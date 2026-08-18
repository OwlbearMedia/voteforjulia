#!/usr/bin/env bash
#
# Substitute the edge token into a built .htaccess, or strip the gate when no
# token is configured. See ADR-0020 and docs/hosting.md.
#
# Runs on the GitHub-hosted runner against the file about to be uploaded, not
# on the host: the runner is ephemeral and single-tenant, and the token has to
# come to rest on the shared host regardless. Keeping it out of the *artifact*
# is what matters, which is why this runs in the deploy job rather than the
# build job.
#
# Usage: EDGE_TOKEN=<token or empty> scripts/arm-edge-gate.sh <path-to-.htaccess>

set -euo pipefail

readonly MIN_TOKEN_LENGTH=32

# The gate exactly as public/.htaccess spells it, newline-joined with `|`.
# Compared whole, because validating only the line the placeholder sits on
# accepts a build that dropped `RewriteRule ^ - [F]` or a path exception and
# refuses nothing -- and a RewriteCond with no rule after it attaches itself to
# whatever rule comes next. Update this in lockstep with public/.htaccess; the
# lockstep is deliberate, so the gate cannot change as a side effect.
readonly EXPECTED_STANZA='RewriteCond %{REQUEST_URI} !^/\.well-known/|RewriteCond %{REQUEST_URI} !^/[Aa]utodiscover/|RewriteCond %{HTTP:X-Origin-Token} !^@@EDGE_TOKEN@@$|RewriteRule ^ - [F]|'

die() {
  echo "arm-edge-gate: $1" >&2
  exit 1
}

main() {
  local staged="${1:-}"
  [ -n "$staged" ] || die "usage: EDGE_TOKEN=<token> $0 <path-to-.htaccess>"
  [ -s "$staged" ] || die "$staged is missing or empty."

  if [ -z "${EDGE_TOKEN:-}" ]; then
    # A missing secret must fail OPEN. Left literal, the placeholder demands a
    # header no caller can send and refuses every visitor.
    sed -i.bak '/# BEGIN EDGE GATE/,/# END EDGE GATE/d' "$staged" && rm -f "$staged.bak"
    echo "EDGE_SHARED_TOKEN unset; edge gate removed, origin left open."
  else
    # Alphanumeric because the value is interpolated into a sed replacement and
    # then a RewriteCond regex, where a metacharacter would corrupt the file or
    # quietly change what the rule matches.
    case "$EDGE_TOKEN" in
      *[!A-Za-z0-9]*) die "EDGE_SHARED_TOKEN must be alphanumeric." ;;
    esac

    # A guessed token is as good as a leaked one, and a caller refused at the
    # origin never reached the edge's rate limiting -- so the 403 is an
    # unmetered oracle. Entropy is the control; see docs/hosting.md.
    [ "${#EDGE_TOKEN}" -ge "$MIN_TOKEN_LENGTH" ] ||
      die "EDGE_SHARED_TOKEN must be at least $MIN_TOKEN_LENGTH characters; got ${#EDGE_TOKEN}."

    local actual occurrences
    actual=$(sed -n '/^# BEGIN EDGE GATE$/,/^# END EDGE GATE$/p' "$staged" | sed '1d;$d' | tr '\n' '|')
    if [ "$actual" != "$EXPECTED_STANZA" ]; then
      echo "arm-edge-gate: staged gate stanza is not the expected block." >&2
      echo "  expected: $EXPECTED_STANZA" >&2
      echo "  actual:   $actual" >&2
      die "If public/.htaccess changed the gate on purpose, update EXPECTED_STANZA to match."
    fi

    # `sed` substitutes the first match on EVERY line, so a second placeholder
    # anywhere else takes the real token with it -- into whatever line it sits
    # on, which for a `Header set` means publishing the secret in a response.
    occurrences=$(grep -o '@@EDGE_TOKEN@@' "$staged" | wc -l | tr -d '[:space:]' || true)
    [ "$occurrences" = "1" ] ||
      die "Expected exactly one @@EDGE_TOKEN@@ in $staged; found $occurrences."

    sed -i.bak "s/@@EDGE_TOKEN@@/$EDGE_TOKEN/" "$staged" && rm -f "$staged.bak"
    echo "Edge gate armed."
  fi

  # Neither branch may leave a placeholder behind: that is the shape of the
  # total-outage failure, so it is worth failing the deploy for.
  ! grep -q '@@EDGE_TOKEN@@' "$staged" ||
    die "Placeholder survived; refusing to upload."

  # The range delete above runs to EOF if the END marker is ever lost,
  # truncating the file to its first few lines. Neither check above catches
  # that: the placeholder is gone either way and the file is still non-empty.
  # Assert something from the far end instead -- losing the CSP silently is
  # what ADR-0010 warns about.
  grep -q 'Content-Security-Policy' "$staged" ||
    die "$staged lost its CSP; refusing to upload."
}

main "$@"
