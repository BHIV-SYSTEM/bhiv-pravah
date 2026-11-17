from executer.executor import attach_execution_id
from executer.guard import validate_caller
from contracts.execution_contract import advance_execution_state, validate_execution_contract
from pravah_stream.stream import emit

def execute(signal: dict, headers: dict):
    # [SECURITY] enforce caller
    signal = validate_caller(signal, headers)

    execution_contract_data = signal.get("execution_contract")
    if execution_contract_data:
        execution_contract = validate_execution_contract(execution_contract_data, signal)
        execution_contract = advance_execution_state(execution_contract, "EXECUTED")
        execution_contract = advance_execution_state(execution_contract, "COMPLETED")
        signal["execution_contract"] = execution_contract.model_dump(mode="json")
        signal["execution_id"] = execution_contract.execution_id

    # [OK] attach execution_id
    signal = attach_execution_id(signal)

    # [OK] simulate execution (replace later with real logic)
    signal["status"] = "success"

    # [EMIT] emit to pravah
    emit(signal)
    print("[EXECUTER] EXECUTER CALLED")
    return signal