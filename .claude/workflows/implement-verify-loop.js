export const meta = {
  name: 'implement-verify-loop',
  description: 'Codex implements a file-described task, an adversarial reviewer verifies it against the task letter and spirit, and on failure a git-tracked constructor + alternating refine loop builds a self-contained follow-up task for a fresh Codex run, up to 5 iterations.',
  whenToUse: 'Invoke with args: {"taskFile": "/abs/path/to/task.md"}. Reusable: the task lives only in the file, never in these prompts.',
  phases: [
    { title: 'Implement', detail: 'Codex (xhigh, danger sandbox) applies the current task' },
    { title: 'Review', detail: 'adversarial verify of done-claims and not-done reasons' },
    { title: 'Reconstruct', detail: 'git-tracked constructor + alternating refine loop builds the next task' },
  ],
}

const MAX_OUTER = 5
const MAX_REFINE = 5

const T0 = args.taskFile
const createdFiles = []

const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'stdoutFile', 'stderrFile'],
  properties: {
    exitCode: { type: 'integer', description: 'The exit code Codex returned (the EXIT=$? value), not your own status.' },
    stdoutFile: { type: 'string', description: 'Absolute path of the temp file capturing Codex stdout ($out).' },
    stderrFile: { type: 'string', description: 'Absolute path of the temp file capturing Codex stderr ($err).' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['pass', 'reportPath'],
  properties: {
    pass: { type: 'boolean', description: 'True only when the implementation meets the task in both letter and spirit.' },
    reportPath: { type: 'string', description: 'Absolute path of the review report you wrote ($r).' },
  },
}

const CONSTRUCT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['taskFile', 'dir'],
  properties: {
    taskFile: { type: 'string', description: 'Absolute path of the task file you wrote ($dir/task.md).' },
    dir: { type: 'string', description: 'Absolute path of the git repo holding the task ($dir).' },
  },
}

const REFINE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['noEditsApplied'],
  properties: {
    noEditsApplied: { type: 'boolean', description: 'True if the draft was already solid and you committed no change; false if you edited and committed.' },
    createdFiles: { type: 'array', items: { type: 'string' }, description: 'Absolute paths of any temp files you created (e.g. Codex stdout/stderr); [] if none.' },
  },
}

const implementPrompt = (taskFile) => `You drive the Codex CLI to implement a task described in a file. You implement nothing yourself.

1. Create two temp files: out=$(tempfile codex-stdout.md); err=$(tempfile codex-stderr.log)
2. Run Codex with the task file as its prompt on stdin, and capture the exit code:
   codex exec --skip-git-repo-check -m "gpt-5.5" --config model_reasoning_effort="xhigh" --sandbox danger-full-access --full-auto - < "${taskFile}" > "$out" 2> "$err"; echo "EXIT=$?"
3. Do not retry, edit, or second-guess Codex.`

const reviewPrompt = (taskFile, reportFile) => `You are an adversarial reviewer. The task is described in ${taskFile}; an implementer (Codex) acted on it and wrote a report to ${reportFile}.

The report is a starting point, not ground truth. It typically claims some items done and explains why others were not.
- For every "done" claim: verify it against the actual repository state (inspect files, run checks). Do not trust the claim.
- For every "not done, because <reason>" claim: adversarially scrutinise whether the reason is legitimate. Do not bother proving the item is absent.
- Judge against both the letter and the spirit of the task.

Write your findings to r=$(tempfile review-report.md).`

const constructPrompt = (t0, tk, rk, vk) => `The current attempt failed review. Construct the next task for a fresh Codex run.

Inputs (paths):
- Original task, the immutable source of truth for scope, form and spirit: ${t0}
- Task used this iteration: ${tk}
- Implementer report: ${rk}
- Review report, the authoritative gap list: ${vk}

Produce ONE self-contained task (a future reader needs no other file). It must:
- Cover every requirement of the original task: as a "must hold" item if already implemented, or a "to do" item if still missing or wrong.
- Match the form and spirit of the original task.

Track it in git so its evolution and rationale are traceable:
  dir=$(mktemp -d)
  (write the task to "$dir/task.md" with your file-writing tool)
  git -C "$dir" init -q && git -C "$dir" add -A && git -C "$dir" commit -q -m "<concise reasoning for this draft>"`

const refinePrompt = (mode, dir, taskFile, t0, tk, rk, vk) => {
  const edit = mode === 'codex'
    ? `Make the edits by running Codex (xhigh) over the file, then commit them yourself:
  o=$(tempfile refine-codex-stdout.md); e=$(tempfile refine-codex-stderr.log)
  codex exec --skip-git-repo-check -m "gpt-5.5" --config model_reasoning_effort="xhigh" --sandbox workspace-write --full-auto -C "${dir}" "Refine ${taskFile} so it is self-contained and faithfully preserves every requirement of the original task ${t0} (as must-hold or to-do), in its form and spirit; use ${vk} and ${rk} for context." > "$o" 2> "$e"`
    : `Edit ${taskFile} directly with your file-editing tools.`
  return `You verify, and if needed refine, a draft task file. The draft must be self-contained and must faithfully carry the original task's full scope (every original requirement present as "must hold" or "to do"), in the original's form and spirit.

Draft: ${taskFile} (inside git repo ${dir}).
References: original task ${t0}; task used last iteration ${tk}; implementer report ${rk}; review report ${vk}.

First read the draft's history and rationale so you do not undo earlier decisions blindly:
  git -C "${dir}" log -p

Then decide:
- If the draft is solid, change nothing.
- If it is deficient (not self-contained, drops or distorts an original requirement, or mis-splits must-hold vs to-do), fix it. ${edit}
  Commit with a concise reasoning: git -C "${dir}" add -A && git -C "${dir}" commit -q -m "<why you changed it>"`
}

let task = T0

for (let k = 1; k <= MAX_OUTER; k++) {
  phase('Implement')
  const impl = await agent(implementPrompt(task), {
    label: `codex-impl#${k}`, phase: 'Implement', model: 'opus', schema: IMPL_SCHEMA,
  })
  createdFiles.push(impl.stdoutFile, impl.stderrFile)
  if (impl.exitCode !== 0) {
    return { status: 'halted', iteration: k, exitCode: impl.exitCode, stdoutFile: impl.stdoutFile, stderrFile: impl.stderrFile, createdFiles }
  }

  phase('Review')
  const review = await agent(reviewPrompt(task, impl.stdoutFile), {
    label: `review#${k}`, phase: 'Review', model: 'opus', schema: REVIEW_SCHEMA,
  })
  createdFiles.push(review.reportPath)
  if (review.pass) {
    return { status: 'passed', iterations: k, reportPath: review.reportPath, createdFiles }
  }
  if (k === MAX_OUTER) {
    return { status: 'exhausted', iterations: k, lastReportPath: review.reportPath, createdFiles }
  }

  phase('Reconstruct')
  const built = await agent(constructPrompt(T0, task, impl.stdoutFile, review.reportPath), {
    label: `construct#${k}`, phase: 'Reconstruct', model: 'opus', schema: CONSTRUCT_SCHEMA,
  })
  createdFiles.push(built.taskFile)
  const draft = built.taskFile
  const dir = built.dir

  for (let j = 1; j <= MAX_REFINE; j++) {
    const mode = j % 2 === 1 ? 'codex' : 'opus'
    const refined = await agent(refinePrompt(mode, dir, draft, T0, task, impl.stdoutFile, review.reportPath), {
      label: `refine#${k}.${j}:${mode}`, phase: 'Reconstruct', model: 'opus', schema: REFINE_SCHEMA,
    })
    if (refined.createdFiles?.length) createdFiles.push(...refined.createdFiles)
    if (refined.noEditsApplied) break
  }

  task = draft
}
