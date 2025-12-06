#!/usr/bin/env python3
"""Fix indentation in server.py"""
with open('server.py', 'r') as f:
    lines = f.readlines()

# Fix the get_recent_cgm_readings method (lines 249-279)
fixed = []
for i, line in enumerate(lines):
    line_num = i + 1
    if line_num == 255:  # end_time line - needs indentation
        fixed.append('            end_time = datetime.now()\n')
    elif line_num == 256:  # start_time line - needs indentation
        fixed.append('            start_time = end_time - timedelta(minutes=minutes_back)\n')
    elif line_num == 254:  # Empty line after session
        fixed.append('            \n')
    elif line_num == 257:  # Empty line before results
        fixed.append('            \n')
    elif line_num == 258:  # results line - already has indentation but check
        if not line.startswith('            '):
            fixed.append('            ' + line.lstrip())
        else:
            fixed.append(line)
    else:
        fixed.append(line)

with open('server.py', 'w') as f:
    f.writelines(fixed)
    
print('Fixed indentation')

