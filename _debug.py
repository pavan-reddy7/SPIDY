import sys; sys.path.insert(0, 'src')
from tool_base import ToolRegistry
reg = ToolRegistry()
reg.discover('src/tools')
tool = reg.get('search_contents')
result = tool.execute(target="xxxxxxxxxxxxnosuchtextyyyy12345 in C:\\SPIDY")
print(repr(result.message[:200]))
print("success:", result.success)
