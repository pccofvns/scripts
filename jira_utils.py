from argparse import ArgumentParser

from github_pull_request_utils import *

JIRA_DEV_RESOLUTION_COMMENT_KEYS = [PULL_REQUEST_TITLE, DESCRIPTION_OF_CHANGES, TESTS, PULL_REQUEST_LINKS, REVIEWER_USERNAMES, DATABASE_CHANGES, PROPERTY_CHANGES]

jira_rest_api_url = 'https://jira.mycompany.com/rest/api/latest'
JIRA_CUSTOM_FIELD_XYZ = 'customfield_12345'
header = '''{panel:title=Dev Resolution Comments|borderStyle=dashed|borderColor=#cccccc|titleBGColor=#f7d6c1|bgColor=#ffffce}'''
footer = '''{panel}'''


def parse_cli_arguments():
    args = {}
    parser = ArgumentParser()
    parser.add_argument('-j', '--jira', dest='issue_key', action='store', type=str,
                        required=False,
                        help='JIRA issue key')
    parser.add_argument('-T', '--jt', dest='jt', action='store', type=str,
                        required=False,
                        help='JIRA Token to be used for reading/updating issue details via REST API')
    args.update(parser.parse_args().__dict__)
    return args


def get_jira_headers(args):
    return {"Authorization": "Bearer " + args['jt'], "Content-Type": "application/json"}


def get_issue_details(args, issue_key):
    jira_issue = None
    if args.get('jt'):
        jira_issue = requests.get(jira_rest_api_url + "/issue/" + issue_key, headers=get_jira_headers(args)).json()
    elif args.get('jira_username') and args.get('jira_password'):
        jira_issue = requests.get(jira_rest_api_url + "/issue/" + issue_key,
                                  auth=(args['jira_username'], args['jira_password']),
                                  headers={"Content-Type": "application/json"}).json()
    elif os.environ['JIRA_TOKEN']:
        args['jt'] = os.environ['JIRA_TOKEN']
        jira_issue = requests.get(jira_rest_api_url + "/issue/" + issue_key,
                                  headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'],
                                           "Content-Type": "application/json"}).json()
    return jira_issue


def get_issue_details_with_token(issue_key):
    return requests.get(jira_rest_api_url + "/issue/" + issue_key,
                                  headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'],
                                           "Content-Type": "application/json"}).json()


def get_user_details(args, user_key):
    jira_user = None
    if args.get('jt'):
        jira_user = requests.get(jira_rest_api_url + "/user/search?username=" + user_key, headers=get_jira_headers(args)).json()
    elif args.get('jira_username') and args.get('jira_password'):
        jira_user = requests.get(jira_rest_api_url + "/user/search?username=" + user_key,
                                auth=(args['jira_username'], args['jira_password']),
                                headers={"Content-Type": "application/json"}).json()
    elif os.environ['JIRA_TOKEN']:
        args['jt'] = os.environ['JIRA_TOKEN']
        jira_user = requests.get(jira_rest_api_url + "/user/search?username=" + user_key,
                                headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'],
                                         "Content-Type": "application/json"}).json()
    return jira_user[0]


def get_issue_type(args, issue_key):
    issue_key = issue_key.strip()
    jira_issue = None
    print(f'Getting issue type for {issue_key}')
    if args.get('jt'):
        print('Using JIRA token from command line arguments')
        jira_issue = requests.get(jira_rest_api_url + "/issue/" + issue_key + "?fields=issuetype,parent",
                                  headers=get_jira_headers(args)).json()
    elif args.get('jira_username') and args.get('jira_password'):
        print('Using JIRA username and password from command line arguments')
        jira_issue = requests.get(jira_rest_api_url + "/issue/" + issue_key + "?fields=issuetype,parent",
                                  auth=(args['jira_username'], args['jira_password']),
                                  headers={"Content-Type": "application/json"}).json()
    else:
        print('Using JIRA token from environment variables')
        try:
            jira_issue_response = requests.get(jira_rest_api_url + "/issue/" + issue_key + "?fields=issuetype,parent",
                                               headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'],
                                                        "Content-Type": "application/json"})
            jira_issue_response.raise_for_status()
            jira_issue = jira_issue_response.json()
        except Exception as e:
            print(f'Error occurred while getting issue details for {issue_key}. Error: {e}')
        print(f'JIRA issue details for {issue_key}')
    if jira_issue:
        print(f'{jira_issue}')
        issue_type = jira_issue['fields']['issuetype']['name']
        if issue_type == "Sub-task" or issue_type == "Dev Task" or issue_type == "DB Task":
            issue_key = jira_issue['fields']['parent']['key']
            return get_issue_type(args, issue_key), issue_key
        return jira_issue['fields']['issuetype']['name'], issue_key
    else:
        print(f'Unable to get issue details for {issue_key}')
        return None, issue_key


def post_comment(args, issue_key, dev_resolution_template):
    if args.get('jt'):
        jira_issue = requests.post(jira_rest_api_url + "/issue/" + issue_key + "/comment",
                                   headers=get_jira_headers(args), json={"body": dev_resolution_template})
    else:
        jira_issue = requests.post(jira_rest_api_url + "/issue/" + issue_key + "/comment",
                                   auth=(args['jira_username'], args['jira_password']),
                                   headers={"Content-Type": "application/json"}, json={"body": dev_resolution_template})
    print(f'Comment added to JIRA issue {issue_key}')
    return jira_issue


def post_comment_on_jira_with_token(issue_key, dev_resolution_template):
    jira_issue = requests.post(jira_rest_api_url + "/issue/" + issue_key + "/comment",
                               headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'], "Content-Type": "application/json"}, json={"body": dev_resolution_template})
    print(jira_issue)
    print(f'Comment added to JIRA issue {issue_key}')
    return jira_issue


def post_update(args, issue_key, fields):
    fields_to_update = {"fields": fields}
    if args.get('jt'):
        jira_issue = requests.put(jira_rest_api_url + "/issue/" + issue_key, headers=get_jira_headers(args),
                                  json=fields_to_update)
    else:
        jira_issue = requests.put(jira_rest_api_url + "/issue/" + issue_key,
                                  auth=(args['jira_username'], args['jira_password']),
                                  headers={"Content-Type": "application/json"}, json=fields_to_update)
    print(f'Fields updated to JIRA issue {issue_key} are\n {fields}')
    return jira_issue


def post_update_on_jira_with_token(issue_key, fields):
    fields_to_update = {"fields": fields}
    jira_issue = requests.put(jira_rest_api_url + "/issue/" + issue_key, headers={"Authorization": "Bearer " + os.environ['JIRA_TOKEN'], "Content-Type": "application/json"},
                                  json=fields_to_update)
    print(f'Fields updated to JIRA issue {issue_key} are\n {fields}')
    return jira_issue


def is_defect(issue):
    return issue['fields']['issuetype']['name'] == "Defect"


def populate_jira_custom_field(pull_request_details, issue, fields):
    rca = pull_request_details.get(RCA)
    if is_defect(issue) and rca:
        if issue['fields'][JIRA_CUSTOM_FIELD_XYZ] and rca not in issue['fields'][JIRA_CUSTOM_FIELD_XYZ]:
            rca = issue['fields'][JIRA_CUSTOM_FIELD_XYZ] + "\n" + rca
            fields[JIRA_CUSTOM_FIELD_XYZ] = rca
        elif not issue['fields'][JIRA_CUSTOM_FIELD_XYZ]:
            fields[JIRA_CUSTOM_FIELD_XYZ] = rca
    return fields


def markdown_checkboxes_to_jira_syntax(text):
    text = text.replace("- [ ]", "(x)")
    text = text.replace("- [x]", "(/)")
    return text


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


def populate_jira_comment(pull_request_details):
    pull_request_details[REVIEWERS] = ', '.join(pull_request_details[REVIEWER_USERNAMES])
    jira_comment = header + "\n"
    for key in JIRA_DEV_RESOLUTION_COMMENT_KEYS:
        jira_comment = jira_comment + "|*" + \
                       key + "*|" + transform_text_from_markdown_to_jira_syntax(pull_request_details[key]) + "|\n"
    jira_comment = jira_comment + footer
    pull_request_details['jira_comment'] = jira_comment


def main():
    # Parse CLI arguments
    args = parse_cli_arguments()
    # Generate dev resolution template
    pull_request_details = generate_pull_request_details(args)
    populate_jira_comment(pull_request_details)
    # Get issue details
    issue_key = args['issue_key']
    if issue_key:
        # TODO: If you want to post custom fields, uncomment below lines and modify the code accordingly
        # issue = get_issue_details(args, issue_key)
        # fields = {}
        # populate_jira_custom_field(pull_request_details, issue, fields)
        # if fields:
        #     post_update(args, issue_key, fields)
        if pull_request_details['jira_comment']:
            post_comment(args, issue_key, pull_request_details['jira_comment'])
    else:
        print(pull_request_details['jira_comment'])


if __name__ == "__main__":
    main()
