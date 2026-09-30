from backend.plugins.base_plugin import BasePlugin

class HelloWorldPlugin(BasePlugin):
    def get_tools(self):
        return [
            {
                "name": "hello_greet",
                "description": "hello_greet | No args - Returns a friendly greeting from the Hello World plugin."
            },
            {
                "name": "hello_reverse",
                "description": "hello_reverse | text=<string> - Reverses the provided string."
            }
        ]

    def execute(self, tool_name: str, kwargs: dict) -> str:
        if tool_name == "hello_greet":
            return "Greetings from the Hello World Plugin! The sandbox is working!"
        elif tool_name == "hello_reverse":
            text = kwargs.get("text", "")
            return text[::-1]
        
        return "Unknown tool in HelloWorld plugin."
