import click

import python_graphql_compiler

context_settings = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=context_settings)
@click.version_option(python_graphql_compiler.__version__, "--version")
def cli():
    pass


@cli.command()
@click.argument("arg")
@click.option(
    "--repeat", metavar="N", type=int, default=1, help="Repeat N times (optional)."
)
def echo(arg, repeat):
    for _ in range(repeat):
        click.echo(arg)


def main():
    cli()


if __name__ == "__main__":
    main()
