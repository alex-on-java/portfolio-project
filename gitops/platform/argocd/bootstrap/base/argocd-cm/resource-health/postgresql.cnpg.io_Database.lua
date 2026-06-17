hs = {}

if obj.status == nil then
  hs.status = "Progressing"
  hs.message = "Waiting for Database status"
  return hs
end

if obj.metadata == nil or obj.metadata.generation == nil then
  hs.status = "Progressing"
  hs.message = "Waiting for Database metadata generation"
  return hs
end

if obj.status.observedGeneration == nil then
  hs.status = "Progressing"
  hs.message = "Waiting for Database observed generation"
  return hs
end

if tostring(obj.status.observedGeneration) ~= tostring(obj.metadata.generation) then
  hs.status = "Progressing"
  hs.message = obj.status.message or "Waiting for Database controller to observe latest generation"
  return hs
end

if obj.status.applied == true then
  hs.status = "Healthy"
  hs.message = obj.status.message or "Database has been applied"
  return hs
end

if obj.status.applied == false then
  hs.status = "Degraded"
  hs.message = obj.status.message or "Database has not been applied"
  return hs
end

hs.status = "Progressing"
hs.message = obj.status.message or "Waiting for Database applied status"
return hs
