import re

with open('backend/planning/planner.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''        s3 = TaskStep(
            step_id="step_3_verify",
            description=f"Verify completion of: '{goal}'",
            action_type="verify",
            required_agent="system_agent",
            dependencies=["step_2_execute"],
            risk_level=RiskLevel.LOW
        )
        return [s1, s2, s3]'''

content = re.sub(r'        s3 = TaskStep\(.*?return \[s1, s2, s3\]', '        return [s1, s2]', content, flags=re.DOTALL)
content = content.replace('        return [s1, s2]', replacement)

with open('backend/planning/planner.py', 'w', encoding='utf-8') as f:
    f.write(content)
