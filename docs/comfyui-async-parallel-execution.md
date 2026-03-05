# ComfyUI 노드 비동기 병렬 실행 가이드

## 문제

ComfyUI 실행 엔진은 노드를 **위상 정렬 순서대로 순차 실행**한다. 데이터 의존성이 없는 독립 노드들도 하나씩 실행되므로, I/O-bound 작업(외부 API 호출 등)이 포함된 워크플로에서 불필요한 대기가 발생한다.

```
[Generate A] ──image──→ [Edit]
[Generate B] ──image──→ [Edit]
```

위 구조에서 Generate A와 B는 독립적이지만 순차 실행된다. 각 API 호출이 10초라면, 총 20초가 소요된다.

## 해결: async execute

ComfyUI 실행 엔진은 `async def execute()`를 **네이티브로 지원**한다. execute가 코루틴이면 `asyncio.Task`로 생성하고, 즉시 완료되지 않으면 `PENDING` 상태로 전환하여 다른 노드로 실행을 넘긴다.

### 실행 흐름

```
1. Node A (async execute) 시작 → asyncio.Task 생성 → PENDING 반환
2. 실행 엔진이 다음 ready 노드(Node B)로 이동
3. Node B (async execute) 시작 → asyncio.Task 생성 → PENDING 반환
4. 두 Task가 동시에 실행됨 (I/O 대기 중 이벤트 루프가 번갈아 처리)
5. 모든 Task 완료 → unblock → 후속 노드(Edit) 실행
```

총 소요 시간: ~10초 (20초 → 10초, 2배 개선)

## 핵심 메커니즘 (ComfyUI 내부)

### 1. Task 생성 — `execution.py:_async_map_node_over_list()`

```python
# execution.py L281-292
if inspect.iscoroutinefunction(f):
    task = asyncio.create_task(async_wrapper(f, prompt_id, unique_id, index, args=inputs))
    await asyncio.sleep(0)  # Task에 실행 기회 부여
    if task.done():
        results.append(task.result())  # 즉시 완료 시 결과 직접 저장
    else:
        results.append(task)  # 미완료 시 Task 객체 저장
```

`execute()`가 코루틴이면 `asyncio.Task`로 래핑한다. `sleep(0)`으로 한 번 양보한 뒤, 완료되지 않았으면 Task 객체 자체를 results에 저장한다.

### 2. PENDING 처리 — `execution.py:get_output_data()`

```python
# execution.py L332-338
return_values = await _async_map_node_over_list(...)
has_pending_task = any(isinstance(r, asyncio.Task) and not r.done() for r in return_values)
if has_pending_task:
    return return_values, {}, False, has_pending_task
```

results에 미완료 Task가 있으면 `has_pending_task = True`로 반환한다.

### 3. 외부 블록 등록 — `execution.py:execute()`

```python
# execution.py L532-540
if has_pending_tasks:
    pending_async_nodes[unique_id] = output_data
    unblock = execution_list.add_external_block(unique_id)
    async def await_completion():
        tasks = [x for x in output_data if isinstance(x, asyncio.Task)]
        await asyncio.gather(*tasks, return_exceptions=True)
        unblock()
    asyncio.create_task(await_completion())
    return (ExecutionResult.PENDING, None, None)
```

- `pending_async_nodes`에 노드를 등록하고 `PENDING` 반환
- `add_external_block()`으로 해당 노드를 실행 목록에서 차단
- 별도 Task가 `asyncio.gather()`로 모든 하위 Task 완료를 대기
- 완료 시 `unblock()` 호출 → 실행 엔진이 재방문하여 결과 수집

### 4. 결과 수집 — 재진입

```python
# execution.py L434-447
if unique_id in pending_async_nodes:
    results = []
    for r in pending_async_nodes[unique_id]:
        if isinstance(r, asyncio.Task):
            results.append(r.result())  # 완료된 Task에서 결과 추출
        else:
            results.append(r)
    del pending_async_nodes[unique_id]
    output_data, output_ui, has_subgraph = get_output_from_returns(results, class_def)
```

### 5. V3 async classmethod 지원

```python
# comfy_api/internal/__init__.py L132-150
def make_locked_method_func(type_obj, func, class_clone):
    method = getattr(type_obj, func).__func__
    if asyncio.iscoroutinefunction(method):
        async def wrapped_async_func(**inputs):
            return await method(locked_class, **inputs)
        return wrapped_async_func
```

V3 API의 `@classmethod`도 async를 올바르게 래핑한다. `iscoroutinefunction` 체크가 유지되므로 `inspect.iscoroutinefunction(f)` 검사를 통과한다.

## 구현 패턴

### 기본: 동기 함수를 ThreadPoolExecutor로 래핑

외부 SDK가 동기 API만 제공하는 경우 (대부분의 경우):

```python
import asyncio
from comfy_api.latest import io

class MyAsyncNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="My_AsyncNode",
            # ...
        )

    @classmethod
    async def execute(cls, prompt: str, config: dict) -> io.NodeOutput:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # 기본 ThreadPoolExecutor 사용
            lambda: sync_api_call(prompt, config)
        )
        return io.NodeOutput(result)
```

`run_in_executor(None, ...)`는 기본 `ThreadPoolExecutor`를 사용한다. I/O-bound 작업(HTTP 요청, 파일 I/O)에 적합하다.

### 고급: 네이티브 async SDK 사용

SDK가 async를 지원하는 경우 (aiohttp, httpx 등):

```python
@classmethod
async def execute(cls, prompt: str) -> io.NodeOutput:
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, json={"prompt": prompt}) as resp:
            data = await resp.json()
    return io.NodeOutput(data["image"])
```

이벤트 루프를 직접 사용하므로 스레드 오버헤드가 없다.

### 주의사항: CPU-bound 작업

CPU-bound 작업은 `run_in_executor`를 써도 GIL 때문에 진정한 병렬이 되지 않는다. 이 패턴은 **I/O-bound 작업에만 효과적**이다.

```python
# CPU-bound — GIL로 인해 병렬 이점 없음
await loop.run_in_executor(None, lambda: heavy_tensor_computation(image))

# I/O-bound — 네트워크 대기 중 다른 Task 실행 가능
await loop.run_in_executor(None, lambda: requests.post(api_url, json=payload))
```

GPU 연산(`torch` 등)은 GIL을 해제하므로 `run_in_executor`로 병렬 효과를 얻을 수 있으나, GPU 메모리 경합에 주의해야 한다.

## 적용 대상 판단

| 조건 | 적용 여부 |
|------|-----------|
| 외부 API 호출 (REST, gRPC) | 적용 |
| 파일 다운로드 / 업로드 | 적용 |
| 데이터베이스 쿼리 | 적용 |
| GPU 연산 (모델 추론) | 주의 (메모리 경합) |
| CPU-bound 연산 (numpy 등) | 비적용 (GIL) |

## 실제 적용 예시: Vertex Image Generate

### Before (동기, 순차 실행)

```python
@classmethod
def execute(cls, model, config, prompt, seed) -> io.NodeOutput:
    images, text = model.generate_image(prompt, config, seed=seed)
    # ...
    return io.NodeOutput(images, text, ui=ui.PreviewImage(images))
```

### After (비동기, 병렬 실행)

```python
import asyncio

@classmethod
async def execute(cls, model, config, prompt, seed) -> io.NodeOutput:
    loop = asyncio.get_event_loop()
    images, text = await loop.run_in_executor(
        None, lambda: model.generate_image(prompt, config, seed=seed)
    )
    # ...
    return io.NodeOutput(images, text, ui=ui.PreviewImage(images))
```

변경 포인트:
1. `def execute` → `async def execute`
2. `import asyncio` 추가
3. 동기 API 호출을 `await loop.run_in_executor(None, lambda: ...)` 로 래핑

나머지 코드(입력 검증, 에러 처리, NodeOutput 반환)는 변경 없다.
