#!/usr/bin/python
from cpm.option import OptionParser
from cpm import init
from cpm import *
import sys

if sys.version_info < (2, 3):
    sys.exit("error: python 2.3 or later required")

VERSION = "0.0.1"

HELP = """\
Usage: cpm command [options] [arguments]

Available commands:
    query
    install
    upgrade
    remove
    update
    channel
    flag
    config

Run "cpm command --help" for more information.
"""

def parse_options(argv):
    parser = OptionParser(help=HELP, version=VERSION)
    parser.disable_interspersed_args()
    parser.add_option("--config-file", metavar="FILE",
                      help="configuration file (default is ~/.cpm/config)")
    parser.add_option("--data-dir", metavar="DIR",
                      help="data directory (default is ~/.cpm/)")
    parser.add_option("--log-level", metavar="LEVEL",
                      help="set the log level to LEVEL (debug, info, "
                           "warning, error)")
    parser.add_option("--gui", action="store_true",
                      help="use the default graphic interface")
    parser.add_option("--interface",
                      help="use the given interface")
    opts, args = parser.parse_args()
    if args:
        opts.command = args[0]
        opts.argv = args[1:]
    else:
        opts.command = None
        opts.argv = []
    return opts

def main(argv):
    try:
        opts = parse_options(argv)
        ctrl = init(opts)
        iface.start()
        if not opts.command:
            iface.run(ctrl)
        else:
            try:
                cpm = __import__("cpm.commands."+opts.command)
                commands = getattr(cpm, "commands")
                command = getattr(commands, opts.command)
            except (ImportError, AttributeError):
                from cpm.const import DEBUG
                if opts.log_level == DEBUG:
                    import traceback
                    traceback.print_exc()
                raise Error, "invalid command '%s'" % opts.command
            cmdopts = command.parse_options(opts.argv)
            opts.__dict__.update(cmdopts.__dict__)
            command.main(opts, ctrl)
        iface.finish()
        ctrl.saveSysConf()
    except Error, e:
        if opts.log_level == "debug":
            import traceback
            traceback.print_exc()
        if iface.object:
            iface.error(str(e))
        else:
            sys.stderr.write("error: %s\n" % e)
        sys.exit(1)
    except KeyboardInterrupt:
        if opts.log_level == "debug":
            import traceback
            traceback.print_exc()
            sys.exit(1)
        sys.stderr.write("\nInterrupted\n")
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])

# vim:ts=4:sw=4:et
