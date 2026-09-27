#!/bin/sh
# Compatibility shim (Saturday hooks): forward to the dispatcher as a plain trace event.
exec sh "$(dirname "$0")/origit-hook.sh" trace
