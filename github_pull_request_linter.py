from jira_utils import *
import re

DEFAULT_TEST_CASE_RUN_MESSAGE = "This the detail of the first test case that you've run. You can add more below."

issue_pattern = '^(JIRA|MYPROJECT|TECHOPS)-[0-9]+$'
properties = {}
commit_regex = r'^(feat|fix|docs|style|refactor|perf|test|ops|chore|ci)(\(\w+\))?!?:\s.*$'
conventional_commit_types = ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'ops', 'chore', 'ci']
jira_issue_type_conventional_commit_type_mapping = {
    'User Story': 'feat',
    'Defect': 'fix',
    'Task': 'chore',
    'Epic': 'feat',
}
branch_name_conventional_commit_type_mapping = {
    'feature': 'feat',
    'hotfix': 'fix',
    'bug': 'fix',
    'enhancement': 'feat',
    'story': 'feat',
    'task': 'chore',
    'automation': 'feat',
    'epic': 'feat',
    'defect': 'fix',
    'documentation': 'docs',
}
non_compliant_texts = [
    '<!--- Root Cause Analysis. The title of the story shall be enough in case the changes are related to a user story -->',
    '<!--- Describe the code changes done to implement the story or to fix the defect-->',
    '<!--- Describe the impact of this change on other modules and/features -->',
    'JIRA-0000'
]


def lint():
    pull_request = {}
    pr_title_path = Path(properties['pt'])
    pr_title = pr_title_path.read_text()
    pr_body_path = Path(properties['pb'])
    pr_body = pr_body_path.read_text()

    # check for unwanted texts in PR body
    unwanted_texts = collect_non_compliant_texts(pr_body)
    if unwanted_texts:
        eprint(f'Found below unwanted text(s) in PR body')
        for unwanted_text in unwanted_texts:
            eprint(f'\'{unwanted_text}\'')
        eprint(f'Please remove the unwanted text(s) from PR body')
        return False

    new_pr_title = ' '.join(pr_title.strip().split())
    new_pr_title = re.sub(r'\w+/', '', new_pr_title)
    new_pr_title = capitalize_jira_project_name(new_pr_title)
    new_pr_title = ' '.join(new_pr_title.split())
    new_pr_title = re.sub(r'\w+/', '', new_pr_title)
    new_pr_title = new_pr_title.strip()
    issue_keys_in_title = find_specific_issue_keys(new_pr_title)
    pull_request[DESCRIPTION_OF_CHANGES] = extract_description_from_pr_body(pr_body)
    pull_request[ISSUES] = extract_issue_ticket_numbers_from_pr_body(pr_body)
    pull_request[TESTS] = extract_tests_from_pr_body(pr_body)
    populate_sub_headings_of_description(pull_request, pull_request[DESCRIPTION_OF_CHANGES])
    # check if any of these two subheadings are same
    if pull_request[RCA] == pull_request[CODE_CHANGES] or pull_request[RCA] == pull_request[IMPACT_ANALYSIS] or pull_request[CODE_CHANGES] == pull_request[IMPACT_ANALYSIS]:
        eprint(f'Root Cause Analysis, Code Changes, and Impact Analysis should be different')
        return False
    if not issue_keys_in_title or len(issue_keys_in_title) == 0:
        eprint(f'Missing JIRA number in title \'{pr_title}\'')
        issue_keys_in_pr_body = find_specific_issue_keys(pull_request[ISSUES].strip())
        remove_unwanted_issue_keys(issue_keys_in_pr_body)
        if len(issue_keys_in_pr_body) == 0:
            eprint(f'Missing JIRA number in PR body and title')
            return False
        else:
            new_pr_title = update_pr_title_with_issue_key(issue_keys_in_pr_body, issue_keys_in_title, new_pr_title)
    if DESCRIPTION_OF_CHANGES_HEADING not in pr_body or ISSUE_TICKET_NUMBER_HEADING not in pr_body or TESTS_HEADING not in pr_body:
        eprint(f'Missing mandatory sections "## Description of Changes", "## Issue ticket number(s)", and "## Tests" in PR body')
        return False

    is_valid_pr = validate(pull_request)
    if not is_valid_pr:
        return False
    pr_update_needed = False
    if new_pr_title != pr_title:
        print(f'PR title needs to be updated to: {new_pr_title}')
        pr_update_needed = True
    is_conventional_commit = is_valid_conventional_commit(pr_title)
    print(f'Is conventional commit: {is_conventional_commit}')
    if not pr_update_needed and is_conventional_commit:
        print('PR title is already in conventional commit format and no update is needed')
        return True

    if not is_conventional_commit:
        print(f'PR title \'{new_pr_title}\' is not in conventional commit format')
        conventional_commit_type = get_conventional_commit_type(issue_keys_in_title)
        new_pr_title = conventional_commit_type + ': ' + new_pr_title
        print(f'Will have to update PR title to: {new_pr_title}')
        pr_update_needed = True

    # Update GitHub PR title using GitHub REST API via Python requests module
    if pr_update_needed:
        print(f'PR update needed. Updating PR title to: {new_pr_title}')
        update_pull_request_title(new_pr_title)
    return True


def update_pr_title_with_issue_key(issue_keys_in_pr_body, issue_keys_in_title, new_pr_title):
    issue_keys_in_title.append(issue_keys_in_pr_body[0])
    for conventional_commit_type in conventional_commit_types:
        if new_pr_title.startswith(conventional_commit_type + ':'):
            pr_tile_parts = new_pr_title.split(conventional_commit_type + ':')
            pr_tile_parts.insert(1, issue_keys_in_title[0] + ':')
            new_pr_title = ' '.join(pr_tile_parts)
            break
        else:
            new_pr_title = issue_keys_in_title[0] + ': ' + new_pr_title.strip()
            break
    return new_pr_title


def capitalize_jira_project_name(pr_title):
    text = pr_title
    for project in specified_projects_keys:
        # Create a regex pattern to match any prefix followed by the project name and a numerical ID
        pattern = re.compile(r'(\S+)?\s*(' + project + r')\s+(\d+)', re.IGNORECASE)
        # Replace the found pattern with the correct format
        text = pattern.sub(lambda m: (m.group(1) + ' ' if m.group(1) else '') + m.group(2).upper() + '-' + m.group(3), text)
    return text


def get_conventional_commit_type(issue_keys_in_title):
    branch_name = os.environ['BRANCH_NAME']
    print(f'Branch name: {branch_name}')
    conventional_commit_type = get_commit_type_from_branch_name(branch_name)
    issue_key = issue_keys_in_title[0]
    if 'TECHOPS' in issue_key:
        conventional_commit_type = 'ops'
    original_issue_key = issue_keys_in_title[0]
    print('Tried with Pull Request and branch name, could not decide on type of this change')
    if not conventional_commit_type:
        print('Need to update PR title using JIRA details to match conventional commit pattern')
        try:
            issue_type, issue_key = get_issue_type({}, issue_key)
            print(f'Issue type: {issue_type} and issue key: {issue_key} and original issue key: {original_issue_key}')
            if not conventional_commit_type:
                conventional_commit_type = jira_issue_type_conventional_commit_type_mapping[issue_type]
        except Exception as e:
            eprint(f'Unable to determine conventional commit type for issue key {issue_key}. Error: {e}')
    if not conventional_commit_type:
        eprint(f'Unable to determine conventional commit type for issue key {issue_key}')
        conventional_commit_type = 'chore'
    print(f'Conventional commit type: {conventional_commit_type}')
    return conventional_commit_type


def get_commit_type_from_branch_name(branch_name):
    conventional_commit_type = None
    for commit_type in conventional_commit_types:
        if commit_type.lower() in branch_name.lower():
            print(f'Found commit type {commit_type} in conventional commit type branch name {branch_name}')
            return commit_type

    if not conventional_commit_type and "/" in branch_name:
        for br_name, commit_type in branch_name_conventional_commit_type_mapping.items():
            if br_name.lower() in branch_name.split("/")[0].lower():
                print(f'Found commit type {commit_type} in branch name {branch_name}')
                return commit_type
    return None


def validate(pull_request):
    if DESCRIPTION_OF_CHANGES not in pull_request or not pull_request[DESCRIPTION_OF_CHANGES].strip():
        eprint(f'Mandatory sections "Description of Changes" can not be empty')
        return False
    if TESTS not in pull_request or not pull_request[TESTS].strip() or DEFAULT_TEST_CASE_RUN_MESSAGE in pull_request[TESTS]:
        eprint(f'Mandatory section "Tests" can not be empty or default message')
        return False
    if RCA not in pull_request or not pull_request[RCA].strip():
        eprint(f'Mandatory sub-section "RCA" can not be empty')
        return False
    if CODE_CHANGES not in pull_request or not pull_request[CODE_CHANGES].strip():
        eprint(f'Mandatory sub-section "Code Changes" can not be empty')
        return False
    if IMPACT_ANALYSIS not in pull_request or not pull_request[IMPACT_ANALYSIS].strip():
        eprint(f'Mandatory sub-section "Impact Analysis" can not be empty')
        return False
    issues_text = pull_request[ISSUES]
    issues = find_specific_issue_keys(issues_text)
    if len(issues) != 0 and ('JIRA-0000' in issues):
        eprint('Invalid Issues JIRA-0000')
        return False
    # verify issue using regex pattern
    print(f'Identified Issues from PR body: {issues}')
    return True


def is_valid_conventional_commit(message):
    """Check if the commit message is valid according to the conventional commits pattern."""
    return re.match(commit_regex, message.strip()) is not None


def collect_non_compliant_texts(text):
    found_texts = []
    for non_compliant_text in non_compliant_texts:
        if non_compliant_text in text:
            found_texts.append(non_compliant_text)
    return found_texts


def parse_cli_arguments():
    parser = ArgumentParser()
    parser.add_argument('-t', '--pt', dest='pt', action='store', type=str,
                        required=True, help='Path to Pull Request title file')
    parser.add_argument('-b', '--pb', dest='pb', action='store', type=str,
                        required=True, help='Path to Pull Request body file')
    properties.update(parser.parse_args().__dict__)


def main():
    try:
        parse_cli_arguments()
        success = lint()
        if success:
            print('PR is valid')
            sys.exit(0)
        else:
            eprint('PR is invalid')
            sys.exit(1)
    except Exception as e:
        eprint(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
