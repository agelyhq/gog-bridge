# gog-bridge documentation

The [project README](../README.md) says what this server is and why it exists. These pages say
how to drive it.

## The set

**[getting-started.md](getting-started.md)** takes you from a machine with gog signed in to a
first command answered inside Claude Desktop: install with `uvx`, the three environment
variables, the client config, a first `gog_run`, then a first `gog_help`. Read it first.

**[tools.md](tools.md)** is the reference for `gog_run` and `gog_help`: every parameter, the
exact shape of the report that comes back, what a non-zero exit looks like on the client side,
the capture caps, the timeout, and the policy rule by rule with the argument forms it catches.
Open it when you know what you want and need the contract.

**[troubleshooting.md](troubleshooting.md)** is organised by symptom rather than by cause,
because the symptom is what you have when something breaks. A server that does not start, a
refusal in French, a timeout, a truncated listing, a `.cmd` wrapper that survives its kill, an
account error that is gog's and not the bridge's.

## When something goes wrong

Go to [troubleshooting.md](troubleshooting.md) first. Every failure this server reports arrives
as an MCP tool error with a readable message, and the message says which of three things
happened: the policy refused the call before anything ran, gog ran and exited non-zero, or gog
could not be started at all. The first two are for the calling model to act on; the third is for
whoever wrote the configuration.

## What is not here

There is no deployment guide, because there is nothing to deploy: the server speaks MCP over
stdio and your client starts it. There is no HTTP mode, no container image and no port. There is
also no guide to gog itself: `gog_help` prints the help of the installed version, which is the
only one that matters, and the [gogcli repository](https://github.com/openclaw/gogcli) holds the
rest.
