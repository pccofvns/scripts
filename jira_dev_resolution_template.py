from getpass import getpass

from jira_utils import *

jira_url = 'https://jira.mycompany.com'
jira_rest_api_url = 'https://jira.mycompany.com/rest/api'
jira_pat_url = 'https://jira.mycompany.com//rest/pat/latest/tokens'


def parse_cli_arguments():
    args = {}
    parser = ArgumentParser()
    parser.add_argument('-p', '--pr', nargs='+', dest='pr', action='store', type=str,
                        required=True, help='The Pull Request number')
    parser.add_argument('-j', '--jira', dest='issue_key', action='store', type=str,
                        required=False,
                        help='JIRA ticket ID. If provided, then jira username and password id also required')
    parser.add_argument('-U', '--username', dest='jira_username', action='store', type=str,
                        required=False, help='JIRA Username')
    parser.add_argument('-P', '--password', dest='jira_password', action='store', type=str,
                        required=False, help='JIRA Password')
    parser.add_argument('-T', '--jt', dest='jt', action='store', type=str,
                        required=False,
                        help='JIRA Token to be used for reading/updating issue details via REST API')
    parser.add_argument('-r', '--repo', dest='repo', action='store', type=str,
                        required=False,
                        help='Name of github repository. If not given, then it is retrived from config `remote.origin.url`')
    parser.add_argument('-t', '--gt', dest='gt', action='store', type=str,
                        required=False,
                        help='Github Token to be used for reading PR details via REST API. If not provided, then falls back to ~/.git-credentials file.')
    parser.add_argument('-m', '--mode', dest='mode', action='store', type=str,
                        required=False,
                        default='cli',
                        help='Request Mode. Possible values: github and cli. Default is cli')
    args.update(parser.parse_args().__dict__)
    return args


def init_jira_auth(args):
    if args.get('jt'):
        return args['jt']
    if args['mode'] == 'cli':
        username = args.get('jira_username')
        password = args.get('jira_password')
        if not username:
            args['jira_username'] = input("Enter your Jira username: ")
        if not password:
            args['jira_password'] = getpass("Enter your Jira password: ")
    if args['mode'] == 'github':
        return os.environ['JIRA_TOKEN']
    # jira_pat_body = '{"name": "' + getuser() + '_jira_cli' + '","expirationDuration": 365}'
    # requests.post(jira_pat_url, headers={"Content-Type": "application/json"}, data=jira_pat_body, auth=(username, password))


def post_resolution_comment(args, context):
    new_comment = '```\n' + context['jira_comment'] + '\n```'
    add_comment_to_github_issue(new_comment)


def main():
    # Parse CLI arguments
    args = parse_cli_arguments()
    # Generate dev resolution template
    context = generate_pull_request_details(args)
    # Get issue details
    issue_key = args['issue_key']
    if issue_key:
        init_jira_auth(args)
        issue = get_issue_details(args, issue_key)
        fields = populate_jira_fields(args, context, issue)
        if fields:
            post_update(args, issue_key, fields)
        if context['jira_comment']:
            post_comment(args, issue_key, context['jira_comment'])
    else:
        print(context['jira_comment'])
        if args['mode'] == 'github':
            post_resolution_comment(args, context)
            for issue_key in context[ISSUE_KEYS]:
                if context['jira_comment']:
                    post_comment_on_jira_with_token(str(issue_key), context['jira_comment'])
                issue = get_issue_details_with_token(issue_key)
                if issue:
                    fields = {}
                    populate_jira_impact_analysis(context, issue, fields)
                    if fields:
                        try:
                            post_update_on_jira_with_token(issue_key, fields)
                        except Exception as e:
                            print('Error while updating issue: ', issue_key, e)


def populate_jira_fields(args, context, issue):
    fields = {}
    # TODO: If and when need to post update to fields
    # populate_jira_custom_field(context, issue, fields)
    return fields


if __name__ == "__main__":
    main()
