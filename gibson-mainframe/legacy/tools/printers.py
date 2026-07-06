from termcolor import colored

# In this file: funtions that just print pretty stuff

def print_menu(scripts):
    # Print the main menu
    print(colored("\nCHOOSE FROM A CATEGORY:", "yellow"))
    categories = list(scripts.keys())[:10]  # Only display the first 10 categories
    for i in range(len(categories)):
        print(f"{i+1}. {categories[i]}")
    print()

def print_sub_menu(category, scripts):
    # Print a sub-menu
    alternating_colour = "blue"

    print(f"\n{category}:")
    if len(scripts) > 10 and category != "Saved":
        #print into 2 columns if there are more than 10 scripts in the results
        middle = int(len(scripts) / 2)
        for i in range(middle):
            print(colored("{}. {: >30} {: >12}. {: >30}".format(i+1, scripts[i][:-4], middle+i+1, scripts[middle+i][:-4]), alternating_colour))
                
            if alternating_colour == "blue":
                alternating_colour = "green"
            else:
                alternating_colour = "blue"

        #if the number was odd, need to print an extra single script
        if len(scripts) % 2 != 0:
            print(colored("{} {: >30} {: >12}. {: >30}".format("   ", "", middle+i+1+1, scripts[middle+i+1][:-4]), "green"))

    else:
        #if there are 10 or less scripts, don't bother with the columns
        for i in range(len(scripts)):
            print(colored(f"{i+1}. {scripts[i]}", alternating_colour))
            if alternating_colour == "blue":
                alternating_colour = "green"
            else:
                alternating_colour = "blue"

#generate the report
def generate_report(output, script, target, output_file, screen_output):
    vulnerabilities = ["vuln", "exploit", "risk", "danger", "warning", "critical", "high", 
                       "medium", "low", "Insecure", "dangerous",
                       "Anonymous FTP Login", "State: VULNERABLE", "EOL", "Windows 2000",
                       "Windows NT", "Windows 2003", "Windows 2008", "Out of Support", "Login Success"]
    
    if target != "":
        report = f"Penetration Testing Report for target {target} using {script}:\n"
    else:
        report = f"Penetration Testing Report for target using {script}:\n"

    if any(vulnerability.lower() in output.lower() for vulnerability in vulnerabilities):
        report += "The scan has identified potential vulnerabilities. It is recommended to investigate these findings further and apply necessary patches or configuration changes to mitigate any risk."
    else:
        report += "The scan did not identify any obvious vulnerabilities. However, this does not guarantee the security of the system. Regular scans and updates are recommended."

    report += "\n\nHighlighted lines from the output:\n"
    lines = output.split('\n')

    for vulnerability in vulnerabilities:
        matched_lines = [i for i, line in enumerate(lines) if vulnerability in line]
        for line_index in matched_lines:
            report += "Potential vulnerability found related to '{}':\n".format(vulnerability)
            start = max(0, line_index - 3)
            end = min(len(lines), line_index + 4)
            for i in range(start, end):
                report += lines[i] + "\n"

    if output_file:
        with open(output_file, 'a') as f:
            f.write("\n\n" + report)

    #if the user said they wanted the output printed to screen, show the report on screen
    #also show the report on screen if there is no output file
    if screen_output == "y" or screen_output == "yes" or output_file == "":
        print(colored("\nReport Output:", "blue"))
        print("================================================================")
        print(report)

def view_output(output):
    # View the output of the command
    print(colored("\nCommand Output:", "blue"))
    print("================================================================")
    lines = output.split('\n')

    # Add new keywords to highlight in red
    red_keywords = ["VULN", "Login Success", "State: VULNERABLE", "Anonymous FTP login allowed", 
                    "Windows NT", "Windows 2000", "Windows 2003", "Windows 2008", "ESXi 6.5.0", "EOL", "out of support", "OUT OF SUPPORT", "Out of Support", "Warning", "dangerous"]

    for i, line in enumerate(lines, start=1):
        if any(keyword in line for keyword in red_keywords):
            print(colored(line, 'red'))
        elif "deprecated" in line:
            print(colored(line, 'yellow'))
        elif "dangerous" in line or "weak" in line:
            print(colored(line, 'magenta'))
        else:
            print(line)
        if i % 20 == 0:
            input('Press Enter to continue...')

def print_script_description(script):
    # Print the description of the script
    script_file = f"/usr/share/nmap/scripts/{script}"
    try:
        with open(script_file, 'r') as f:
            lines = f.readlines()
        description_lines = [line for line in lines if 'description = [[' in line]
        if description_lines:
            start_index = lines.index(description_lines[0])
            description = []
            for line in lines[start_index:]:
                if ']]' in line:
                    description.append(line.split(']]')[0])
                    break
                description.append(line)
            description = ''.join(description).replace('description = [[', '').strip()
            print(f"\n{script}:")
            print(colored(f"{description}", 'blue'))
    except FileNotFoundError:
        print("The script file does not exist.")
    except PermissionError:
        print("You do not have the necessary permissions to read the script file.")
