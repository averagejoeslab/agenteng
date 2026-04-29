import os
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main():
    messages = []

    while True:
        user_input = input("❯ ")
        if user_input.lower() in ("/q", "exit"):
            break

        messages.append({"role": "user", "content": user_input})

        async with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="You are a helpful assistant.",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            print()
            response = await stream.get_final_message()

        messages.append({"role": "assistant", "content": response.content[0].text})


asyncio.run(main())
