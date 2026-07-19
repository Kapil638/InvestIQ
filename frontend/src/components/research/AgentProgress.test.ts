import { describe, expect, it } from 'vitest'
import {
  activeStageIndexFromTrace,
  deriveAgentStageStatuses,
  deriveAgentStageStatusesFromTrace,
} from './AgentProgress'

describe('AgentProgress pipeline trace', () => {
  it('maps backend pipeline_trace to stage statuses', () => {
    const trace = [
      { stage: 'financial', status: 'completed' },
      { stage: 'news', status: 'completed' },
      { stage: 'analysis', status: 'completed' },
      { stage: 'risk', status: 'completed' },
      { stage: 'guardrails', status: 'completed' },
      { stage: 'recommendation', status: 'completed' },
      { stage: 'committee', status: 'completed' },
    ]
    const statuses = deriveAgentStageStatusesFromTrace(trace)
    expect(statuses.risk).toBe('completed')
    expect(statuses.recommendation).toBe('completed')
  })

  it('uses simulated progress only when trace is absent', () => {
    const simulated = deriveAgentStageStatuses(1, {
      loading: true,
      failed: false,
      complete: false,
    })
    expect(simulated.financial).toBe('completed')
    expect(simulated.news).toBe('running')

    const fromTrace = deriveAgentStageStatusesFromTrace([])
    expect(fromTrace.financial).toBe('waiting')
  })

  it('derives active stage index from trace', () => {
    const trace = [
      { stage: 'financial', status: 'completed' },
      { stage: 'news', status: 'completed' },
      { stage: 'analysis', status: 'running' },
    ]
    expect(activeStageIndexFromTrace(trace)).toBe(2)
  })
})
