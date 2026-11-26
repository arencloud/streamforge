-- Merge into central argocd-cm resource.customizations.health.gateway.networking.k8s.io_Gateway.
local hs = {status = "Progressing", message = "Waiting for Gateway Accepted and Programmed"}
local accepted, programmed = false, false
for _, c in ipairs((obj.status or {}).conditions or {}) do
  if c.observedGeneration == obj.metadata.generation and c.status == "True" then
    if c.type == "Accepted" then accepted = true end
    if c.type == "Programmed" then programmed = true end
  end
end
if accepted and programmed then
  return {status = "Healthy", message = "Gateway Accepted and Programmed"}
end
return hs
