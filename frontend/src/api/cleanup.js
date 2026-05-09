import { api, createWs } from './client.js'

export const cleanupApi = {
  listRules:   ()           => api.get('/api/cleanup/rules'),
  startScan:   (ruleNames)  => api.post('/api/cleanup/scan',    { body: { rule_names: ruleNames } }),
  scanWs:      (taskId)     => createWs(`/api/cleanup/scan/ws/${taskId}`),
  startExecute:(paths)      => api.post('/api/cleanup/execute', { body: { paths } }),
  executeWs:   (taskId)     => createWs(`/api/cleanup/execute/ws/${taskId}`),
}
