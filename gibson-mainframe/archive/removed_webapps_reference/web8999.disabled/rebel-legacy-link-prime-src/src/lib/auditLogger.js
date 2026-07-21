import { base44 } from '@/api/base44Client';

/**
 * Central audit logging utility.
 * Call from any screen to record an event.
 */
export async function logAudit({ event_type, operator_id, details, result, affected_entity, row_count, duration_ms }) {
  await base44.entities.AuditLog.create({
    event_type,
    operator_id: operator_id || 'UNKNOWN',
    details,
    result: result || 'SUCCESS',
    affected_entity: affected_entity || '',
    row_count: row_count ?? null,
    duration_ms: duration_ms ?? null,
    terminal_id: 'LT0042',
  });
}