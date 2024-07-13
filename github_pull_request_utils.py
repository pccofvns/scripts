import os
import subprocess
import sys
import re
import requests
from pathlib import Path

# Name of GitHub Organization of project owner
org_name = 'pccofvns'
# List of specified project keys
specified_projects_keys = ['JIRA']
# Supported values, ASCIIDOC. Default MARKDOWN
hyperlink_style = 'JIRA'

# Regular expression pattern for issue keys
# Positive lookbehind assertion to include only specified projects
issue_key_pattern = r'\b(?:' + '|'.join(specified_projects_keys) + r')-\d+\b'
base_url = 'https://api.github.com/repos'
DESCRIPTION_OF_CHANGES = 'Description of Changes'
RCA = 'Root Cause Analysis'
CODE_CHANGES = 'Code Changes'
IMPACT_ANALYSIS = 'Impact Analysis'
REVIEWERS = 'Reviewers'
ISSUES = 'Issues'
ISSUE_KEYS = 'Issue Keys'
TESTS = 'Tests'
REVIEW_COMMENTS = 'Review Comments'
REVIEWER_USERNAMES = 'Reviewer Usernames'
DATABASE_CHANGES = 'Database Changes'
PROPERTY_CHANGES = 'Property Changes'
PULL_REQUEST_LINKS = 'Pull Request Link(s)'
PULL_REQUEST_TITLE = 'Title'

H2 = '##'
H3 = '##'
DESCRIPTION_OF_CHANGES_HEADING = '## Description of Changes'
ISSUE_TICKET_NUMBER_HEADING = '## Issue ticket number(s)'
TESTS_HEADING = '## Tests'
IMPACT_ANALYSIS_HEADING = '### Impact Analysis'
CODE_CHANGES_HEADING = '### Code Changes'
RCA_HEADING = '### RCA'

pull_request_template_headers = ["## Description of Changes", "## Issue ticket number(s)", "## Tests"]
pull_request_template_sub_headers = {"## Description of Changes": ["### RCA", "### Code Changes",
                                                                   "### Impact Analysis"]}


def git_auth_token(args):
    token = None
    token_url = None
    home_dir = Path.home()
    if args.get('gt'):
        token_url = args['gt']
    elif os.path.isfile(home_dir / ".git-credentials"):
        token_url = open(home_dir / ".git-credentials", "r").readline()
    if token_url:
        token = token_url.split(':')[2].replace('@github.com', '').strip()
    if not token:
        token = os.environ['GIT_TOKEN']
    return token


def get_git_headers(args):
    token = git_auth_token(args)
    headers = {"Authorization": "Bearer " + token}
    return headers


def generate_pull_request_details(args):
    pull_request_details = {
        REVIEW_COMMENTS: set(),
        REVIEWER_USERNAMES: set(),
        ISSUE_KEYS: set(),
        DATABASE_CHANGES: False,
        PROPERTY_CHANGES: False
    }
    pr_numbers = args['pr']
    repo_name = get_repo_name(args)
    for pr_num in pr_numbers:
        pr = get_pull_request_details(args, pr_num, repo_name)
        populate_title(pull_request_details, pr['title'])

        populate_pull_request_details_from_pr_body(args, pull_request_details, pr)

        issue_keys = find_specific_issue_keys(pr['title'])
        issue_ticket_numbers_text = extract_issue_ticket_numbers_from_pr_body(pr['body'])
        if issue_ticket_numbers_text:
            issue_keys_in_pr_body = find_specific_issue_keys(issue_ticket_numbers_text.strip())
            remove_unwanted_issue_keys(issue_keys_in_pr_body)
            issue_keys = issue_keys + issue_keys_in_pr_body
        pull_request_details[ISSUE_KEYS].update(set(issue_keys))
    return pull_request_details


def populate_pull_request_details_from_pr_body(args, pull_request_details, pr):
    populate_resolution_summary(pull_request_details, pr['body'])
    populate_test_cases_run(pull_request_details, pr['body'])
    populate_pull_request_links(pr, pull_request_details)
    pr_reviews = get_pull_request_reviews(args, pr['number'], pr['head']['repo']['name'])
    for pr_review in pr_reviews:
        populate_review_details_by_git_review(args, pull_request_details, pr_review)
    pr_files = get_pull_request_files(args, pr['number'], pr['head']['repo']['name'])
    for pr_file in pr_files:
        populate_file_type_changes_from_commits(pull_request_details, pr_file)


def populate_file_type_changes_from_commits(pull_request_details, pr_file):
    if pull_request_details[PROPERTY_CHANGES] is False and (
            ('.properties' in pr_file['filename'].lower() and 'message' not in pr_file[
                'filename'].lower()) or 'ddl' in pr_file['filename'].lower()
            or '_config' in pr_file['filename'].lower()):
        pull_request_details[PROPERTY_CHANGES] = True
    if pull_request_details[DATABASE_CHANGES] is False and '.sql' in pr_file['filename'].lower():
        pull_request_details[DATABASE_CHANGES] = True


def populate_review_details_by_git_review(args, pull_request_details, pr_review):
    username = pr_review['user']['login']
    username_url = create_hyperlink(username, pr_review['user']['html_url'])
    review_comment = pr_review['body']
    issue_management_system_username = username_url
    if hyperlink_style == 'JIRA':
        issue_management_system_username = "[~" + username + "]"
    pull_request_details[REVIEWER_USERNAMES].add(issue_management_system_username)
    if review_comment:
        pull_request_details[REVIEW_COMMENTS].add(issue_management_system_username + ": " + review_comment)


def get_pull_request_files(args, pr_num, repo_name):
    pr_files_response = requests.get(
        base_url + "/" + org_name + "/" + repo_name + "/pulls" + "/" + str(pr_num) + "/files",
        headers=get_git_headers(args))
    pr_files = pr_files_response.json()
    return pr_files


def get_pull_request_reviews(args, pr_num, repo_name):
    pr_review_response = requests.get(
        base_url + "/" + org_name + "/" + repo_name + "/pulls" + "/" + str(pr_num) + "/reviews",
        headers=get_git_headers(args))
    pr_reviews = pr_review_response.json()
    return pr_reviews


def populate_pull_request_links(pr, pull_request_details):
    display_text = str(pr['number'])
    url = pr['html_url']
    hyperlink = create_hyperlink(display_text, url)
    pr_link = hyperlink + "@" + pr['base']['ref'] + " on " + str(pr['merged_at'])
    if PULL_REQUEST_LINKS in pull_request_details:
        pull_request_details[PULL_REQUEST_LINKS] = pull_request_details[PULL_REQUEST_LINKS] + \
                                                   "\n" + pr_link
    else:
        pull_request_details[PULL_REQUEST_LINKS] = pr_link


def create_hyperlink(display_text, url):
    if hyperlink_style == 'JIRA':
        hyperlink = "[#" + display_text + "|" + url + "]"
    elif hyperlink_style == 'ASCIIDOC':
        hyperlink = url + "[" + display_text + "]"
    else:
        hyperlink = "[#" + display_text + "]" + "(" + url + ")"
    return hyperlink


def get_pull_request_details(args, pr_num, repo_name):
    if org_name not in repo_name:
        url = base_url + "/" + org_name + "/" + repo_name + "/pulls" + "/" + pr_num
    else:
        url = base_url + "/" + repo_name + "/pulls" + "/" + pr_num
    pr_response = requests.get(url, headers=get_git_headers(args))
    pr = pr_response.json()
    return pr


def update_pull_request_title(new_pr_title):
    # Update PR Title
    url = base_url + "/" + os.environ['REPO_NAME'] + "/pulls" + "/" + os.environ['PR_NUMBER']
    headers = {
        "Authorization": "Bearer " + git_auth_token({}),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    requests.patch(url, headers=headers, json={"title": new_pr_title.strip()}, allow_redirects=True)


def add_comment_to_github_issue(new_comment):
    # Add comment to GitHub issue
    url = base_url + "/" + os.environ['REPO_NAME'] + "/issues" + "/" + os.environ['PR_NUMBER'] + "/comments"
    headers = {
        "Authorization": "Bearer " + git_auth_token({}),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    return requests.post(url, headers=headers, json={"body": new_comment.strip()}, allow_redirects=True).json()


def get_repo_name(args):
    repo_name = args['repo']
    if not repo_name:
        git_remote = str(subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'], stdout=subprocess.PIPE).stdout).replace("\\n'", "")
        repo_name = os.path.splitext(
            os.path.basename(git_remote))[0]
    return repo_name


def inline_code(text):
    new_string = ""
    back_tick_count = 0
    for char in text:
        if char == "`":
            back_tick_count += 1
            if back_tick_count % 2 == 0:
                new_char = "}}"
            else:
                new_char = "{{"
            new_string += new_char
        else:
            new_string += char
    return new_string


def populate_title(pull_request, issue_title):
    if PULL_REQUEST_TITLE not in pull_request:
        pull_request[PULL_REQUEST_TITLE] = issue_title


def populate_resolution_summary(pull_request, pr_body):
    description = extract_description_from_pr_body(pr_body)
    if DESCRIPTION_OF_CHANGES in pull_request:
        existing_resolution_summary = pull_request[DESCRIPTION_OF_CHANGES]
        if existing_resolution_summary and existing_resolution_summary.strip() != description.strip():
            pull_request[DESCRIPTION_OF_CHANGES] = pull_request[DESCRIPTION_OF_CHANGES] + "\n" + description
        else:
            pull_request[DESCRIPTION_OF_CHANGES] = description
    else:
        pull_request[DESCRIPTION_OF_CHANGES] = description
    populate_sub_headings_of_description(pull_request, description)


def populate_test_cases_run(pull_request, pr_body):
    tests = extract_tests_from_pr_body(pr_body)
    if TESTS in pull_request:
        existing_tests = pull_request[TESTS]
        if existing_tests and existing_tests.strip() != tests.strip():
            pull_request[TESTS] = pull_request[TESTS] + "\n" + tests
        else:
            pull_request[TESTS] = tests
    else:
        pull_request[TESTS] = tests


def extract_description_from_pr_body(pr_body):
    if pull_request_template_headers[0] not in pr_body:
        return None
    return pr_body[pr_body.index(
        pull_request_template_headers[0]) + len(pull_request_template_headers[0]): pr_body.index(
        pull_request_template_headers[1])].strip()


def extract_issue_ticket_numbers_from_pr_body(pr_body):
    if pull_request_template_headers[1] not in pr_body:
        return None
    return pr_body[pr_body.index(pull_request_template_headers[1]) + len(
        pull_request_template_headers[1]): pr_body.index(
        pull_request_template_headers[2])].strip()


def find_specific_issue_keys(text):
    # Find all matches using the pattern
    issue_keys = re.findall(issue_key_pattern, text)
    return issue_keys


def remove_unwanted_issue_keys(issue_keys_in_pr_body):
    if 'JIRA-0000' in issue_keys_in_pr_body:
        issue_keys_in_pr_body.remove('JIRA-0000')


def extract_tests_from_pr_body(pr_body):
    if pull_request_template_headers[2] not in pr_body:
        return None
    return pr_body[pr_body.index(
        pull_request_template_headers[2]) + len(pull_request_template_headers[2]):].strip()


def populate_sub_headings_of_description(pull_request, description):
    if RCA_HEADING in description:
        rca_heading_start = description.index(RCA_HEADING)
        right_part_of_text = description.split(RCA_HEADING)[1]
        if right_part_of_text and right_part_of_text.find(H2) > 0:
            pull_request[RCA] = description[rca_heading_start + 8: description.split(RCA_HEADING)[1].index(
                H2) + rca_heading_start + 7].strip()
        else:
            pull_request[RCA] = description[rca_heading_start + 8:].strip()
    if CODE_CHANGES_HEADING in description:
        code_changes_heading_start = description.index(CODE_CHANGES_HEADING)
        right_part_of_text = description.split(CODE_CHANGES_HEADING)[1]
        if right_part_of_text and right_part_of_text.find(H2) > 0:
            pull_request[CODE_CHANGES] = description[
                                         code_changes_heading_start + 17: description.split(CODE_CHANGES_HEADING)[
                                                                              1].index(
                                             H2) + code_changes_heading_start + 16].strip()
        else:
            pull_request[CODE_CHANGES] = description[code_changes_heading_start + 17:].strip()
    if IMPACT_ANALYSIS_HEADING in description:
        impact_analysis_heading_start = description.index(IMPACT_ANALYSIS_HEADING)
        right_part_of_text = description.split(IMPACT_ANALYSIS_HEADING)[1]
        if right_part_of_text and right_part_of_text.find(H2) > 0:
            pull_request[IMPACT_ANALYSIS] = description[impact_analysis_heading_start + 20:
                                                        description.split(IMPACT_ANALYSIS_HEADING)[1].index(
                                                            H2) + impact_analysis_heading_start + 19].strip()
        else:
            pull_request[IMPACT_ANALYSIS] = description[impact_analysis_heading_start + 20:].strip()


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
