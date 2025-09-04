"""
Check what planner functionality is available
"""
print("=== Planner Availability Check ===")

try:
    from semantic_kernel.planners import StepwisePlanner
    print("✅ StepwisePlanner - AVAILABLE")
except ImportError as e:
    print(f"❌ StepwisePlanner - NOT AVAILABLE: {e}")

try:
    from semantic_kernel.planners import SequentialPlanner
    print("✅ SequentialPlanner - AVAILABLE") 
except ImportError as e:
    print(f"❌ SequentialPlanner - NOT AVAILABLE: {e}")

try:
    from semantic_kernel.planners import ActionPlanner
    print("✅ ActionPlanner - AVAILABLE")
except ImportError as e:
    print(f"❌ ActionPlanner - NOT AVAILABLE: {e}")

# Check what planners are available
try:
    import semantic_kernel.planners as planners
    print("Available planners:", [name for name in dir(planners) if not name.startswith('_')])
except ImportError as e:
    print(f"❌ planners module: {e}")