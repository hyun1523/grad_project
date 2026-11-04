"""Gemini 호출 래퍼.

- 일시적인 오류(429 한도 초과, 503 과부하)는 잠깐 쉬었다가 재시도한다.
- JSON 응답은 코드블록(```)이 섞여 와도 파싱하고, 실패하면 한 번 더 요청한다.
- 테스트에서는 같은 인터페이스(text, json)를 가진 가짜 객체로 바꿔 끼울 수 있다.
"""
import json
import re
import time

DEFAULT_MODEL = "gemini-2.5-flash"
_RETRYABLE = ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "timed out")


class LLMError(Exception):
    """사용자에게 그대로 보여줘도 되는 AI 호출 오류."""


def parse_json(text: str):
    """모델 응답에서 JSON을 꺼낸다. ```json 코드블록이나 앞뒤 설명이 붙어 있어도 처리한다."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 앞뒤에 설명이 붙은 경우: 첫 번째 [ 또는 { 부터 마지막 ] 또는 } 까지
    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    ends = [i for i in (text.rfind("]"), text.rfind("}")) if i != -1]
    if starts and ends and min(starts) < max(ends):
        return json.loads(text[min(starts) : max(ends) + 1])
    raise ValueError("JSON을 찾을 수 없습니다.")


class GeminiLLM:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, client=None, sleep=time.sleep):
        if client is None:
            from google import genai  # 설치 전에도 다른 모듈을 테스트할 수 있게 지연 import

            client = genai.Client(api_key=api_key)
        self.client = client
        self.model = model
        self._sleep = sleep

    def _call(self, prompt: str, json_mode: bool = False, retries: int = 3) -> str:
        config = None
        if json_mode:
            from google.genai import types

            config = types.GenerateContentConfig(response_mime_type="application/json")
        last_err = None
        for attempt in range(retries):
            try:
                kwargs = {"model": self.model, "contents": prompt}
                if config is not None:
                    kwargs["config"] = config
                response = self.client.models.generate_content(**kwargs)
                text = response.text
                if not text:
                    raise LLMError("AI가 빈 응답을 보냈어요. 잠시 후 다시 시도해 주세요.")
                return text
            except LLMError:
                raise
            except Exception as e:  # SDK 예외 종류가 다양해서 메시지로 판별
                last_err = e
                if any(k in str(e) for k in _RETRYABLE) and attempt < retries - 1:
                    self._sleep(2 ** (attempt + 1))
                    continue
                break
        msg = str(last_err)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise LLMError("AI 사용량 한도를 넘었어요. 1분쯤 뒤에 다시 시도해 주세요.")
        if "API key" in msg or "401" in msg or "403" in msg or "PERMISSION" in msg:
            raise LLMError("API 키가 올바르지 않거나 권한이 없어요. .env의 GEMINI_API_KEY를 확인해 주세요.")
        raise LLMError(f"AI 호출 중 오류가 발생했어요: {msg[:200]}")

    def text(self, prompt: str) -> str:
        return self._call(prompt)

    def json(self, prompt: str):
        raw = self._call(prompt, json_mode=True)
        try:
            return parse_json(raw)
        except ValueError:
            # 한 번 더 요청 (형식 오류는 대개 일시적)
            raw = self._call(prompt + "\n\n반드시 유효한 JSON만 출력해.", json_mode=True)
            try:
                return parse_json(raw)
            except ValueError:
                raise LLMError("AI 응답 형식이 올바르지 않아요. 다시 시도해 주세요.")
