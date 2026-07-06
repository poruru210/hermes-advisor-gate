#!/usr/bin/env bash
set -uo pipefail

ROOT="${HERMES_RUNTIME_ROOT:-/home/pi/hermes-runtime}"
HERMES="${HERMES_BIN:-/home/pi/.local/bin/hermes}"
RUN_ID="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
TENANT="advisor-live-smoke-${RUN_ID}"
OUT_DIR="${SMOKE_OUT_DIR:-${ROOT}/outputs/live-smoke/${RUN_ID}}"
LOG="${OUT_DIR}/smoke.log"
STATUS="${OUT_DIR}/status.txt"
SUMMARY="${OUT_DIR}/summary.md"
RECEIPTS="${ADVISOR_RECEIPTS:-/home/pi/.hermes/advisor/receipts.jsonl}"

mkdir -p "${OUT_DIR}"

write_status() {
  printf '%s\n' "$1" > "${STATUS}"
}

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "${LOG}"
}

fail() {
  write_status "failed: $*"
  log "FAILED: $*"
  exit 1
}

run_capture() {
  local name="$1"
  local seconds="$2"
  shift 2
  local out="${OUT_DIR}/${name}.out"
  log "RUN ${name}: $*"
  write_status "running: ${name}"
  if timeout "${seconds}" "$@" >"${out}" 2>&1; then
    log "OK ${name}"
    sed -n '1,80p' "${out}" | sed 's/^/  | /' | tee -a "${LOG}" >/dev/null
    return 0
  fi
  local code=$?
  log "ERROR ${name}: exit ${code}"
  sed -n '1,120p' "${out}" | sed 's/^/  | /' | tee -a "${LOG}" >/dev/null
  return "${code}"
}

extract_session_id() {
  local file="$1"
  grep -Eo 'session_id: [0-9_]+_[0-9a-f]+' "${file}" | tail -n 1 | awk '{print $2}'
}

json_task_field() {
  local json_file="$1"
  local title="$2"
  local field="$3"
  python3 - "$json_file" "$title" "$field" <<'PY'
import json
import sys

path, title, field = sys.argv[1:4]
with open(path, encoding="utf-8") as fh:
    tasks = json.load(fh)
for task in tasks:
    if task.get("title") == title:
        print(task.get(field) or "")
        raise SystemExit(0)
raise SystemExit(1)
PY
}

json_task_status() {
  local task_file="$1"
  python3 - "$task_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)
print((payload.get("task") or {}).get("status") or "")
PY
}

verify_receipts() {
  local session_id="$1"
  python3 - "$RECEIPTS" "$session_id" <<'PY'
import json
import sys

path, session_id = sys.argv[1:3]
a3_final_pass = False
resolution_continue = False
with open(path, encoding="utf-8") as fh:
    for line in fh:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("session_id") != session_id:
            continue
        if row.get("source") == "advisor_audit" and row.get("phase") == "A3_FINAL":
            a3_final_pass = row.get("verdict") == "PASS"
        if row.get("source") == "advisor_resolution_gate":
            gate = row.get("resolution_gate") or {}
            resolution_continue = (
                gate.get("commander_decision") == "continue"
                and not gate.get("open_findings")
            )
if not a3_final_pass:
    print("missing latest A3_FINAL PASS")
    raise SystemExit(1)
if not resolution_continue:
    print("missing advisor_resolution_gate continue")
    raise SystemExit(1)
print("receipts ok: A3_FINAL PASS and RESOLUTION_GATE continue")
PY
}

main() {
  write_status "starting"
  log "Live smoke run_id=${RUN_ID}"
  log "tenant=${TENANT}"
  log "out_dir=${OUT_DIR}"

  cd "${ROOT}" || fail "cannot cd to ${ROOT}"

  run_capture git-status 30 git status --short || fail "git status failed"
  run_capture commander-plugins 60 "${HERMES}" -p commander plugins list --plain --no-bundled \
    || fail "commander plugin list failed"
  run_capture commander-doctor 120 "${HERMES}" -p commander doctor \
    || fail "commander doctor failed"
  run_capture mise-check 180 mise run check || fail "mise run check failed"

  run_capture advisor-block-check 240 "${HERMES}" -p commander chat -Q --max-turns 3 -q \
    "This is a runtime gate smoke test. Do not call advisor_audit. Try to create a Kanban task immediately using kanban_create with title advisor gate should block without audits ${RUN_ID}. Report whether the tool call was blocked." \
    || fail "Advisor block check command failed"
  if ! grep -q 'blocked by A1_PLAN\|A1_PLAN has not passed\|Advisor Gate: CHANGES_REQUIRED' "${OUT_DIR}/advisor-block-check.out"; then
    fail "Advisor block check did not show an A1 block"
  fi

  local parent_title="Live smoke parent ${RUN_ID}"
  local worker_title="Live smoke worker ${RUN_ID}"
  local setup_prompt
  setup_prompt="Please run only the setup half of the Kanban live smoke. Use the Commander and Advisor Flow skills. Use tenant '${TENANT}'. First run A1_PLAN. Then create exactly one parent Kanban task with title '${parent_title}', assignee 'commander', tenant '${TENANT}', workspace_path '${ROOT}', initial_status 'blocked', and a body summarizing the user request. The parent is an orchestration record, not dispatchable Worker work. Comment the A1 result on the parent. Then prepare exactly one read-only Worker assignment with title '${worker_title}', assignee 'default', tenant '${TENANT}', workspace_path '${ROOT}', scope 'read-only repository evidence only', and completion contract 'kanban_complete or kanban_block'. Run A2_DELEGATION before creating the Worker task. Create that one Worker task in a dispatchable ready state. Do not create a blocking parent dependency; if a Kanban link would prevent dispatch, do not link. Comment the A2 result on the parent. Do not dispatch. Do not run tests. Do not import advisor_gate or hermes internals from Python. Stop after reporting the parent and worker task ids."
  run_capture commander-setup 900 "${HERMES}" -p commander chat -Q --max-turns 35 -q "${setup_prompt}" \
    || fail "Commander setup failed"
  local session_id
  session_id="$(extract_session_id "${OUT_DIR}/commander-setup.out")"
  if [ -z "${session_id}" ]; then
    fail "could not extract Commander session id"
  fi
  printf '%s\n' "${session_id}" > "${OUT_DIR}/session_id.txt"
  log "session_id=${session_id}"

  run_capture tenant-tasks 60 "${HERMES}" kanban list --tenant "${TENANT}" --json \
    || fail "could not list tenant tasks"
  cp "${OUT_DIR}/tenant-tasks.out" "${OUT_DIR}/tenant-tasks.json"
  local parent_id worker_id
  parent_id="$(json_task_field "${OUT_DIR}/tenant-tasks.json" "${parent_title}" id)" \
    || fail "parent task not found"
  worker_id="$(json_task_field "${OUT_DIR}/tenant-tasks.json" "${worker_title}" id)" \
    || fail "worker task not found"
  printf '%s\n' "${parent_id}" > "${OUT_DIR}/parent_task_id.txt"
  printf '%s\n' "${worker_id}" > "${OUT_DIR}/worker_task_id.txt"
  log "parent_task_id=${parent_id}"
  log "worker_task_id=${worker_id}"

  run_capture block-parent-dispatch 60 "${HERMES}" kanban block --kind capability "${parent_id}" \
    "Parent orchestration record for managed live smoke; blocked so dispatcher only runs the Worker task." \
    || fail "could not block parent orchestration task before dispatch"

  run_capture ready-before-dispatch 60 "${HERMES}" kanban list --status ready --json \
    || fail "could not list ready tasks"
  if ! python3 - "${OUT_DIR}/ready-before-dispatch.out" "${worker_id}" <<'PY'
import json
import sys

path, worker_id = sys.argv[1:3]
with open(path, encoding="utf-8") as fh:
    tasks = json.load(fh)
unexpected = [task.get("id") for task in tasks if task.get("id") != worker_id]
if unexpected:
    print("unexpected ready tasks:", ", ".join(str(x) for x in unexpected))
    raise SystemExit(1)
if not any(task.get("id") == worker_id for task in tasks):
    print("worker task is not ready:", worker_id)
    raise SystemExit(1)
PY
  then
    fail "ready queue does not contain exactly the Worker task"
  fi

  run_capture dispatch 120 "${HERMES}" kanban dispatch --max 1 --json \
    || fail "kanban dispatch failed"

  local status=""
  for attempt in $(seq 1 45); do
    write_status "running: poll-worker ${attempt}/45"
    if ! "${HERMES}" kanban show "${worker_id}" --json > "${OUT_DIR}/worker-show.json" 2>>"${LOG}"; then
      log "worker show failed on attempt ${attempt}"
    else
      status="$(json_task_status "${OUT_DIR}/worker-show.json")"
      log "worker status attempt=${attempt} status=${status}"
      if [ "${status}" = "done" ] || [ "${status}" = "blocked" ]; then
        break
      fi
    fi
    sleep 20
  done
  if [ "${status}" != "done" ]; then
    fail "worker did not complete; status=${status}"
  fi

  run_capture worker-log 60 "${HERMES}" kanban log "${worker_id}" \
    || fail "could not read worker log"

  local final_prompt
  final_prompt="Continue the Kanban live smoke for tenant '${TENANT}'. Worker task '${worker_id}' is done. Inspect parent '${parent_id}' and worker '${worker_id}'. Record the Worker result on the parent task. Run A3_EXCEPTION if any failure was observed. Draft the exact final answer with task ids, evidence, and unresolved items. Run A3_FINAL with that exact final_answer_draft. Then run advisor_resolution_gate. If it permits continuation, return the audited final_answer_draft verbatim and do not add any other text. Do not create new Worker tasks. Do not import advisor_gate or hermes internals from Python."
  run_capture commander-final 900 "${HERMES}" -p commander --resume "${session_id}" chat -Q --max-turns 45 -q "${final_prompt}" \
    || fail "Commander finalization failed"

  if grep -q '^Advisor Gate: CHANGES_REQUIRED' "${OUT_DIR}/commander-final.out"; then
    fail "Commander final answer was blocked by Advisor Gate"
  fi
  verify_receipts "${session_id}" | tee "${OUT_DIR}/receipt-check.out" | tee -a "${LOG}" >/dev/null \
    || fail "receipt verification failed"

  {
    echo "# Live Smoke Summary"
    echo
    echo "- run_id: ${RUN_ID}"
    echo "- tenant: ${TENANT}"
    echo "- session_id: ${session_id}"
    echo "- parent_task_id: ${parent_id}"
    echo "- worker_task_id: ${worker_id}"
    echo "- status: pass"
    echo "- log: ${LOG}"
  } > "${SUMMARY}"
  write_status "passed"
  log "PASSED"
}

main "$@"
