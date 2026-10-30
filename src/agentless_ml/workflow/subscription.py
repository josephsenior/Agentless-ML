"""Text-only subscription responses using Grinta's saved ChatGPT authorization."""

import json
import os
import subprocess
from pathlib import Path

WORKER = """
import json,sys
from openai import OpenAI
from backend.inference.clients.chatgpt_plan_auth import access_token
request=json.load(sys.stdin)
client=OpenAI(api_key=access_token(request['profile']),base_url='https://api.openai.com/v1',max_retries=0,timeout=request['timeout'])
items={}
text_parts={}
with client.responses.create(model=request['model'],input=[{'role':'user','content':request['prompt']}],reasoning={'effort':request['reasoning']},store=False,stream=True) as stream:
 for event in stream:
  if event.type in ('response.failed','response.incomplete','error'):
   raise RuntimeError('Subscription response failed or was incomplete')
  if event.type=='response.output_item.done':
   items[event.output_index]=event.item
  if event.type=='response.output_text.delta':
   key=(event.output_index,event.content_index)
   text_parts[key]=text_parts.get(key,'')+event.delta
  if event.type=='response.output_text.done':
   text_parts[(event.output_index,event.content_index)]=event.text
  if event.type=='response.completed':
   response=event.response
   def text_of(output):
    return ''.join(part.text for item in output if item.type=='message' for part in item.content if part.type=='output_text')
   text=text_of(items[k] for k in sorted(items)) or text_of(response.output) or ''.join(text_parts[k] for k in sorted(text_parts))
   print(json.dumps({'text':text,'usage':response.usage.model_dump() if response.usage else None,'model':response.model,'stream_output_items':len(items),'stream_text_characters':sum(len(v) for v in text_parts.values())}))
   break
 else:
  raise RuntimeError('Subscription stream ended before completion')
"""


class SubscriptionResponses:
    @property
    def settings(self):
        return {
            "model": self.model,
            "reasoning": self.reasoning,
            "authentication": "chatgpt-plan",
            "profile": self.profile,
            "timeout_seconds": self.timeout,
        }

    def __init__(
        self,
        grinta_root,
        *,
        model="gpt-6.1-sol",
        reasoning="medium",
        profile="default",
        timeout=120,
    ):
        self.root = Path(grinta_root).resolve()
        self.python = (
            self.root
            / ".venv"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        self.model, self.reasoning, self.profile, self.timeout = (
            model,
            reasoning,
            profile,
            timeout,
        )
        if not self.python.is_file():
            raise ValueError("Grinta Python environment not found")

    def complete(self, prompt, *, remaining_seconds=None):
        timeout = (
            self.timeout
            if remaining_seconds is None
            else min(self.timeout, remaining_seconds)
        )
        result = subprocess.run(
            [str(self.python), "-c", WORKER],
            cwd=self.root,
            input=json.dumps(
                {
                    "prompt": prompt,
                    "model": self.model,
                    "reasoning": self.reasoning,
                    "profile": self.profile,
                    "timeout": timeout,
                }
            ),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout if remaining_seconds is not None else timeout + 60,
            check=False,
        )
        if result.returncode:
            # Never copy transport diagnostics or credential-bearing exceptions.
            raise RuntimeError(
                "Subscription response failed; check Grinta sign-in and plan allowance"
            )
        response = json.loads(result.stdout)
        # Stage semantics belong to the controller. In particular, an empty
        # regression-selection response validly means no tests are excluded.
        # Return completed responses before validation so usage is retained.
        return response
