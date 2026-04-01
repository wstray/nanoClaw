from deepagents import create_deep_agent
import inspect

# Create a test agent
agent = create_deep_agent(model="anthropic:claude-sonnet-4-6")

print("Type:", type(agent))
print("\nMethods:")
for m in dir(agent):
    if not m.startswith('_'):
        print(f"  {m}")

# Check invoke method
print("\nInvoke signature:")
print(inspect.signature(agent.invoke))

# Check astream method
if hasattr(agent, 'astream'):
    print("\nAstream signature:")
    print(inspect.signature(agent.astream))
