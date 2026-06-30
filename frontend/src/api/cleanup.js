import { api, createWs } from './client.js'

export const cleanupApi = {
  diagnose:    ()           => api.get('/api/cleanup/diagnose'),
  runAction:   (action)     => api.post('/api/cleanup/diagnose/action', { body: { action } }),
  listRules:   ()           => api.get('/api/cleanup/rules'),
  startScan:   (ruleNames)  => api.post('/api/cleanup/scan',    { body: { rule_names: ruleNames } }),
  scanWs:      (taskId)     => createWs(`/api/cleanup/scan/ws/${taskId}`),
  startExecute:(paths)      => api.post('/api/cleanup/execute', { body: { paths } }),
  executeWs:   (taskId)     => createWs(`/api/cleanup/execute/ws/${taskId}`),
}
