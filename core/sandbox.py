import io
import contextlib

def run_code(code_string: str) -> str:
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()
    
    safe_globals = {
        "__builtins__": {
            "print": print, "range": range, "len": len, "int": int, 
            "float": float, "str": str, "list": list, "dict": dict, 
            "set": set, "tuple": tuple, "round": round, "min": min, 
            "max": max, "sum": sum, "abs": abs, "pow": pow
        }
    }
    
    try:
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
            exec(code_string, safe_globals)
        output = output_buffer.getvalue()
        error = error_buffer.getvalue()
        if error:
            return f"Erro de Execução:\n{error}"
        return output if output else "Código executado com sucesso (sem output impresso)."
    except Exception as e:
        return f"Erro na Sandbox: {str(e)}"