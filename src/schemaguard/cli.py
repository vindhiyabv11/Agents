import sys

from dotenv import load_dotenv

from .agent import StructuredAgent
from .schemas import WeatherReport
from .tools import build_weather_tool


def main() -> None:
    load_dotenv(override=True)
    prompt = " ".join(sys.argv[1:]) or "What's the weather in Bengaluru?"
    agent = StructuredAgent(tools=[build_weather_tool()])
    report = agent.run(prompt, WeatherReport)
    print(report.model_dump_json(indent=2))
    
    