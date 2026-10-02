"""Fixed reviewed AST additions, independent of the retained source witness."""

CLI_HELPER = '''def _workflow_core_arguments(command):
    executable = command.add_mutually_exclusive_group()
    executable.add_argument("--core-executable", type=Path, help=argparse.SUPPRESS)
    executable.add_argument("--verify-executable", type=Path, help=argparse.SUPPRESS)
    command.add_argument("--core-sha256", help=argparse.SUPPRESS)
    command.add_argument("--core-timeout", type=float, help=argparse.SUPPRESS)
'''

CLI_BRANCH = '''if any(getattr(args, name, None) is not None for name in
           ("core_executable", "verify_executable", "core_sha256", "core_timeout")):
    from biocompiler.workflow_cli import selected_core_command
    return selected_core_command(args, bounded_text=_bounded_text, publish_report=_publish_report)
'''

CLI_REGISTRATION = {
    "workflow": "_workflow_core_arguments(workflow)",
    "replay": "_workflow_core_arguments(replay)",
}
