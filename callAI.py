"""Z.AI chat completion client with native + text-embedded tool call support."""

import json
import re
import subprocess
from openai import OpenAI

# --- Configuration ---
import os
ZAI_API_KEY = "e0d01b64cd4e401799cb60cad9bf0098.YpJP60RfaCKbYr9V"
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"
ZAI_MODEL = "glm-4.5-flash"


def run_bash_command(command: str) -> str:
    """Execute a shell command and return combined stdout/stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n[stderr]: {result.stderr.strip()}"
        return output if output else "(command completed with no output)"
    except subprocess.TimeoutExpired:
        return "(command timed out after 30 seconds)"
    except Exception as e:
        return f"(command failed: {e})"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash_command",
            "description": (
                "Run a shell command on the local Windows system. "
                "Use cmd.exe syntax (e.g., 'echo. > file.txt', 'dir', 'type file.txt'). "
                "Do NOT use Unix-only commands like 'touch', 'ls', or 'cat'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    }
]

SYSTEM_PROMPT = (
    "You are a very friendly, cool, and conversational AI voice assistant named destroyer created by Muhammad Huzaifa Ch, running on Windows. "
    "Keep your responses short, snappy, casual, and spoken-friendly — they will be read aloud. "
    "You embody Muhammad Huzaifa Ch's perspective and background:\n"
    "- Demographics & Background: Born in 2006, resides in Haroonabad, Punjab, Pakistan. 12th-grade ICS student studying Mathematics and Physics. Uses a Dell Latitude E7450 laptop (Intel Core i5 5th Gen, 8GB RAM) and a Dell wired mouse.\n"
    "- Skills & Projects: Python programming (creates custom apps like a Flappy Bird game using the Ursina engine), HTML, CSS, JavaScript front-end exploration, GitHub profile `huzaifach-dev`, AutoCAD, and VS Code.\n"
    "- Social Circle & Friends: Close friend Rehan Khan (exchanged gifts like spinner & Dairy Milk chocolate), friend Adnan, and InterPals language exchange partner Xinyu Long (龙心宇) (username: Huzaifa_Ch).\n"
    "- Personal Interests: Loves playing badminton and creative writing (authored chapters for 'The Order of 19' under pen name H Choudhary).\n"
    "- Learning Style: Prefers visual/auditory video lectures for complex concepts.\n"
    "You have access to the run_bash_command tool for shell commands (use cmd.exe syntax). "
    "Use tools only when the user explicitly asks for a system action. "
    "After a tool runs, summarize the result in one short sentence."
)


def parse_text_tool_call(content: str):
    """Parse a tool call embedded as text (Z.AI fallback format)."""
    match = re.search(
        r"<tool_call>\s*(\w+)\s*"
        r"<arg_key>(\w+)</arg_key>\s*"
        r"<arg_value>(.*?)</arg_value>\s*"
        r"</tool_call>",
        content,
        re.DOTALL,
    )
    if not match:
        return None
    return {
        "name": match.group(1).strip(),
        "arguments": {match.group(2).strip(): match.group(3).strip()},
    }


def call_ai(user_text: str) -> str:
    """Send text to Z.AI and handle tool calls (native + text-embedded fallback)."""
    if not ZAI_API_KEY:
        return "(AI error: ZAI_API_KEY environment variable is not set.)"

    client = OpenAI(api_key=ZAI_API_KEY, base_url=ZAI_BASE_URL)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = client.chat.completions.create(
            model=ZAI_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.8,
        )

        message = response.choices[0].message

        # --- Path A: Native tool calls ---
        if getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                if tool_call.function.name == "run_bash_command":
                    args = json.loads(tool_call.function.arguments)
                    result = run_bash_command(args["command"])
                    print(f"[Bash output]: {result}", flush=True)

                    messages.append(message)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                    follow_up = client.chat.completions.create(
                        model=ZAI_MODEL,
                        messages=messages,
                        temperature=0.8,
                    )
                    return follow_up.choices[0].message.content or "(no response)"

        # --- Path B: Tool call embedded as text ---
        content = message.content or ""
        parsed = parse_text_tool_call(content)

        if parsed and parsed["name"] == "run_bash_command":
            command = parsed["arguments"].get("command", "")
            print(f"[Parsed tool call from text]: {command}", flush=True)
            result = run_bash_command(command)
            print(f"[Bash output]: {result}", flush=True)

            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    f"Tool result for command `{command}`:\n{result}\n\n"
                    "Summarize this in one short sentence for the user."
                ),
            })

            follow_up = client.chat.completions.create(
                model=ZAI_MODEL,
                messages=messages,
                temperature=0.8,
            )
            return follow_up.choices[0].message.content or "(no response)"

        # --- Path C: Plain response ---
        return content or "(no response)"

    except Exception as e:
        return f"(AI error: {e})"