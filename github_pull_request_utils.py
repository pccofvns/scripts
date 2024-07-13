import os
import subprocess
import sys
import re
import requests
from pathlib import Path

# List of specified JIRA project keys
specified_projects = ['JIRA']
# Regular expression pattern for JIRA issue keys
# Positive lookbehind assertion to include only specified projects
jira_pattern = r'\b(?:' + '|'.join(specified_projects) + r')-\d+\b'
base_url = 'https://api.github.com/repos'
## TODO: Change as per your need
org_name = 'pccofvns'
header = '''{panel:title=Dev Resolution Comments|borderStyle=dashed|borderColor=#cccccc|titleBGColor=#f7d6c1|bgColor=#ffffce}'''
footer = '''{panel}'''

TITLE = 'Title'
RESOLUTION_SUMMARY = 'Resolution Summary'
TEST_CASES_RUN = 'Test Cases Run'
PULL_REQUESTS = 'Pull Request(s)'
REVIEWERS = 'Reviewers'
DATABASE_SCHEMA_ALTERED = 'Database Schema Altered'
PROPERTY_CONFIG_CHANGED = 'Property/Config Changed'

DESCRIPTION_OF_CHANGES = 'description_of_changes'
RCA = 'rca'
CODE_CHANGES = 'code_changes'
IMPACT_ANALYSIS = 'impact_analysis'
REVIEWERS_LIST = 'reviewers'
ISSUES = 'issues'
ISSUE_KEYS = 'issue_keys'
REVIEW_COMMENTS = 'review_comments'
REVIEWER_GITHUB_IDS = 'REVIEWER_GITHUB_IDS'

H2 = '##'
H3 = '##'
DESCRIPTION_OF_CHANGES_HEADING = '## Description of Changes'
ISSUE_TICKET_NUMBER_HEADING = '## Issue ticket number(s)'
TESTS_HEADING = '## Tests'
IMPACT_ANALYSIS_HEADING = '### Impact Analysis'
CODE_CHANGES_HEADING = '### Code Changes'
RCA_HEADING = '### RCA'

JIRA_DEV_RESOLUTION_COMMENT_KEYS = [TITLE, RESOLUTION_SUMMARY, TEST_CASES_RUN, PULL_REQUESTS, REVIEWERS, DATABASE_SCHEMA_ALTERED, PROPERTY_CONFIG_CHANGED]

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


def generate_pr_details(args):
    context = {
        REVIEW_COMMENTS: set(),
        REVIEWER_GITHUB_IDS: set(),
        REVIEWERS_LIST: set(),
        ISSUE_KEYS: set(),
        DATABASE_SCHEMA_ALTERED: "No",
        PROPERTY_CONFIG_CHANGED: "No"
    }
    pr_numbers = args['pr']
    repo_name = get_repo_name(args)
    for pr_num in pr_numbers:
        pr = get_pull_request_details(args, pr_num, repo_name)
        populate_title(context, pr['title'])

        populate_pr_context_from_pr_body(args, context, pr)

        issue_keys = find_specific_jira_keys(pr['title'])
        issue_ticket_numbers_text = extract_issue_ticket_numbers_from_pr_body(pr['body'])
        if issue_ticket_numbers_text:
            issue_keys_in_pr_body = find_specific_jira_keys(issue_ticket_numbers_text.strip())
            remove_unwanted_jira_ids(issue_keys_in_pr_body)
            issue_keys = issue_keys + issue_keys_in_pr_body
        context[ISSUE_KEYS].update(set(issue_keys))

    context[REVIEWERS] = ', '.join(context[REVIEWERS_LIST])
    jira_comment = header + "\n"
    for key in JIRA_DEV_RESOLUTION_COMMENT_KEYS:
        jira_comment = jira_comment + "|*" + \
                           key + "*|" + transform_text_from_markdown_to_jira_syntax(context[key]) + "|\n"
    jira_comment = jira_comment + footer
    context['jira_comment'] = jira_comment
    return context


def populate_pr_context_from_pr_body(args, context, pr):
    populate_resolution_summary(context, pr['body'])
    populate_test_cases_run(context, pr['body'])
    populate_pull_request_links(pr, context)
    pr_reviews = get_pull_request_reviews(args, pr['number'], pr['head']['repo']['name'])
    for pr_review in pr_reviews:
        populate_review_details_by_git_review(args, context, pr_review)
    pr_files = get_pull_request_files(args, pr['number'], pr['head']['repo']['name'])
    for pr_file in pr_files:
        populate_file_type_changes_from_commits(context, pr_file)


def populate_file_type_changes_from_commits(context, pr_file):
    if not context[PROPERTY_CONFIG_CHANGED] == "No" and (
            ('.properties' in pr_file['filename'].lower() and 'message' not in pr_file[
                'filename'].lower()) or 'ddl' in pr_file['filename'].lower()
            or '_config' in pr_file['filename'].lower()):
        context[PROPERTY_CONFIG_CHANGED] = "Yes"
    if not context[DATABASE_SCHEMA_ALTERED] == "No" and '.sql' in pr_file['filename'].lower():
        context[DATABASE_SCHEMA_ALTERED] = "Yes"


def populate_review_details_by_git_review(args, context, pr_review):
    username = pr_review['user']['login']
    username_url = "[" + username + "|" + pr_review['user']['html_url'] + "]"
    context[REVIEWER_GITHUB_IDS].add(username)
    review_comment = pr_review['body']
    if username:
        context[REVIEWERS_LIST].add("[~" + username + "]")
        if review_comment:
            context[REVIEW_COMMENTS].add("[~" + username + "] :" + review_comment)
    else:
        context[REVIEWERS_LIST].add(username_url)
        if review_comment:
            context[REVIEW_COMMENTS].add(username + " :" + review_comment)


def get_pull_request_files(args, pr_num, repo_name):
    pr_files_response = requests.get(
        base_url + "/" + org_name + "/" + repo_name + "/pulls" + "/" + str(pr_num) + "/files", headers=get_git_headers(args))
    pr_files = pr_files_response.json()
    return pr_files


def get_pull_request_reviews(args, pr_num, repo_name):
    pr_review_response = requests.get(
        base_url + "/" + org_name + "/" + repo_name + "/pulls" + "/" + str(pr_num) + "/reviews",
        headers=get_git_headers(args))
    pr_reviews = pr_review_response.json()
    return pr_reviews


def populate_pull_request_links(pr, context):
    pr_link = "[#" + \
              str(pr['number']) + "|" + pr['html_url'] + \
              "]" + "@" + pr['base']['ref'] + " on " + str(pr['merged_at'])
    if PULL_REQUESTS in context:
        context[PULL_REQUESTS] = context[PULL_REQUESTS] + \
                                     "\n" + pr_link
    else:
        context[PULL_REQUESTS] = pr_link


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
    # Add comment to github issue
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


def transform_text_from_markdown_to_jira_syntax(text):
    if not text:
        return text
    text = text.replace('**', '*')
    text_lines = text.splitlines()
    for i, line in enumerate(text_lines):
        if line and line.strip().startswith("```"):
            if len(line.strip()) == 3:
                text_lines[i] = "{code}"
            else:
                text_lines[i] = "{code:" + line.strip()[3:].strip() + "}"
        elif line and line.strip().startswith("```"):
            text_lines[i] = "{code}"
        elif line and line.strip().startswith("#####"):
            text_lines[i] = "h5. " + line.strip()[5:]
        elif line and line.strip().startswith("####"):
            text_lines[i] = "h4. " + line.strip()[4:]
        elif line and line.strip().startswith("###"):
            text_lines[i] = "h3. " + line.strip()[3:]
        elif line and line.strip().startswith("##"):
            text_lines[i] = "h2. " + line.strip()[2:]
    text = "\n".join(text_lines)
    text = inline_code(text)
    text = markdown_checkboxes_to_jira_syntax(text)
    text = os.linesep.join([s for s in text.splitlines() if s])
    return text


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


def markdown_checkboxes_to_jira_syntax(text):
    text = text.replace("- [ ]", "(x)")
    text = text.replace("- [x]", "(/)")
    return text


def populate_title(pull_request, issue_title):
    if TITLE not in pull_request:
        pull_request[TITLE] = issue_title


def populate_resolution_summary(pull_request, pr_body):
    description = extract_description_from_pr_body(pr_body)
    pull_request[DESCRIPTION_OF_CHANGES] = description
    if RESOLUTION_SUMMARY in pull_request:
        existing_resolution_summary = pull_request[RESOLUTION_SUMMARY]
        if existing_resolution_summary and existing_resolution_summary.strip() != description.strip():
            pull_request[RESOLUTION_SUMMARY] = pull_request[RESOLUTION_SUMMARY] + "\n" + description
        else:
            pull_request[RESOLUTION_SUMMARY] = description
    else:
        pull_request[RESOLUTION_SUMMARY] = description
    populate_sub_headings_of_description(pull_request, description)


def populate_test_cases_run(pull_request, pr_body):
    tests = extract_tests_from_pr_body(pr_body)
    if TEST_CASES_RUN in pull_request:
        existing_tests = pull_request[TEST_CASES_RUN]
        if existing_tests and existing_tests.strip() != tests.strip():
            pull_request[TEST_CASES_RUN] = pull_request[TEST_CASES_RUN] + "\n" + tests
        else:
            pull_request[TEST_CASES_RUN] = tests
    else:
        pull_request[TEST_CASES_RUN] = tests


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


def find_specific_jira_keys(text):
    # Find all matches using the pattern
    issue_keys = re.findall(jira_pattern, text)
    return issue_keys


def remove_unwanted_jira_ids(issue_keys_in_pr_body):
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
