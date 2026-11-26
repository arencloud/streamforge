-- Merge into central argocd-cm resource.customizations.health.<group>_<kind>.
-- Use for Kafka, KafkaConnect, KafkaConnector, KafkaTopic, KafkaUser,
-- ExternalSecret and Certificate; see docs/gitops.md. Do not replace argocd-cm.
local hs = {status = "Progressing", message = "Waiting for the operator"}
if obj.status ~= nil and obj.status.conditions ~= nil then
  if obj.status.observedGeneration ~= nil and obj.metadata.generation ~= nil
      and obj.status.observedGeneration < obj.metadata.generation then
    return hs
  end
  for _, c in ipairs(obj.status.conditions) do
    if c.type == "Ready" and c.status == "True" then
      if c.observedGeneration == nil or c.observedGeneration == obj.metadata.generation then
        return {status = "Healthy", message = c.message or "Ready"}
      end
    end
    if c.type == "NotReady" and c.status == "True" then
      hs.message = c.message or "Operator is reconciling"
    end
  end
end
return hs
