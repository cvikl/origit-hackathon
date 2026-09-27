#!/bin/sh
# Compatibility shim (Saturday hooks): a Stop is the end of a run.
exec sh "$(dirname "$0")/origit-hook.sh" run end
