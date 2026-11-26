// Ejecutar en mongosh. Cambiar erp_agent_demo si se configuró otro nombre.
const audit = db.getSiblingDB('erp_agent_demo').capacity_reports_175932;
audit.find({receipt_id: 'REC-001'}, {_id:1, status:1, reason:1,
  consumed_before:1, consumed_after:1, available_after:1}).sort({reported_at:1});
audit.aggregate([
  {$group: {_id: {status:'$status', reason:'$reason'}, events:{$sum:1}}},
  {$sort: {'_id.status':1, '_id.reason':1}}
]);
// _id impide duplicar un mismo evento. Las cantidades se conservan como texto
// decimal para no convertir NUMERIC a coma flotante en esta proyección.
audit.countDocuments({});
