from __future__ import annotations

import streamlit as st

from core.config import Config


def render_memory_view(profile: str, agent_id: str, memory_service, *, shared_finance: bool) -> None:
    st.subheader("Memórias")
    scope_label = "financeiro compartilhado Allan ↔ Beatriz" if shared_finance else f"privado de {profile}"
    st.caption(f"Mostrando o espaço {scope_label}. Use “lembre que …” no chat para salvar e “esqueça …” para remover por assunto.")

    memories = memory_service.list_authorized(
        profile,
        agent_id,
        shared_finance=shared_finance,
        limit=60,
    )
    if not memories:
        st.info("Nenhuma memória ativa neste espaço.")
        return

    for memory in memories:
        memory_id = str(memory.get("id", ""))
        content = str(memory.get("content", ""))
        memory_type = str(memory.get("memory_type", "fact"))
        importance = float(memory.get("importance", 0.5) or 0.5)
        with st.container(border=True):
            left, right = st.columns([8, 2])
            with left:
                st.markdown(content)
                st.caption(f"{memory_type} · importância {importance:.0%}")
            with right:
                if st.button("Remover", key=f"forget_{memory_id[:16]}", use_container_width=True):
                    if memory_service.forget_authorized(
                        profile,
                        agent_id,
                        memory_id,
                        shared_finance=shared_finance,
                    ):
                        st.success("Memória removida.")
                        st.rerun()
                    st.error("Não foi possível remover essa memória.")


def render_documents_view(profile: str, agent_id: str, process_files, *, shared_finance: bool) -> None:
    from core.profile_access import write_namespace
    from core.vector_rag_v9 import delete_document, list_documents

    st.subheader("Documentos")
    if shared_finance:
        st.caption("Novos documentos serão indexados no espaço financeiro compartilhado Allan ↔ Beatriz.")
    else:
        st.caption(f"Novos documentos serão indexados no espaço privado de {profile} para o agente atual.")

    files = st.file_uploader(
        "Adicionar à base de conhecimento",
        type=["txt", "md", "csv", "json", "pdf", "docx", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="v8_document_uploader",
        help="Até 10 arquivos por vez; limite de 20 MB por arquivo.",
    )
    if st.button("Indexar documentos", type="primary", disabled=not files, use_container_width=True):
        notes, _ = process_files(profile, agent_id, list(files or [])[:10])
        if notes:
            for note in notes:
                st.write(note)
        else:
            st.warning("Nenhum documento foi indexado.")

    namespace = write_namespace(profile, agent_id, shared_finance=shared_finance)
    documents = list_documents(profile=profile, agent_id=agent_id, namespaces=(namespace,))
    st.markdown("#### Documentos indexados")
    if not documents:
        st.caption("Nenhum documento persistido neste espaço.")
        return
    for document in documents:
        with st.container(border=True):
            left, right = st.columns([8, 2])
            with left:
                st.markdown(f"**{document['filename']}**")
                st.caption(f"{document['mime_type']} · {document['chunks']} trecho(s)")
            with right:
                with st.popover("Excluir", use_container_width=True):
                    st.caption("A exclusão remove todos os trechos deste documento.")
                    if st.button("Confirmar exclusão", key=f"delete_doc_{document['namespace']}_{document['file_hash']}", type="primary", use_container_width=True):
                        if delete_document(document["file_hash"], document["namespace"]):
                            st.success("Documento excluído.")
                            st.rerun()
                        st.error("Não foi possível excluir o documento.")


def render_system_view(*, cookie_ready: bool, profile: str, feedback: dict) -> None:
    st.subheader("Sistema")
    st.caption("Diagnóstico seguro. Nenhuma chave ou credencial é exibida.")

    status = Config.status()
    rows = [
        ("DeepSeek", status.get("deepseek", False), "Provider em nuvem"),
        ("Supabase", status.get("supabase", False), "Persistência remota opcional"),
        ("Dispositivo confiável", cookie_ready, "Sessão persistente no navegador"),
    ]

    try:
        from core.llm_router import local_available
        local_ok = bool(local_available())
    except Exception:
        local_ok = False
    rows.append(("Modelo local", local_ok, "Docker Model Runner / Qwen"))

    for name, ok, description in rows:
        with st.container(border=True):
            a, b = st.columns([8, 2])
            with a:
                st.markdown(f"**{name}**")
                st.caption(description)
            with b:
                st.markdown("🟢 OK" if ok else "⚪ Opcional/indisponível")

    st.info("Uma integração opcional indisponível não deve impedir a abertura da interface. O roteador tenta alternativas quando possível.")

    if str(profile).casefold() == "allan":
        from core.telemetry import runtime_snapshot

        snapshot = runtime_snapshot()
        st.markdown("#### Operação desta instância")
        if snapshot["requests"]:
            cols = st.columns(4)
            cols[0].metric("Requisições", snapshot["requests"])
            cols[1].metric("Sucessos", snapshot["successes"])
            cols[2].metric("Fallbacks", snapshot["fallbacks"])
            cols[3].metric("Tempo médio", f"{snapshot['average_duration_ms']} ms")
            st.caption("Métricas mantidas apenas em memória nesta instância; prompts, respostas e identidades não são registrados.")
        else:
            st.caption("Ainda não há requisições registradas nesta instância.")
        st.markdown("#### Feedback deste perfil")
        fcols = st.columns(3)
        fcols[0].metric("Total", int(feedback.get("total", 0)))
        fcols[1].metric("Úteis", int(feedback.get("positive", 0)))
        fcols[2].metric("A melhorar", int(feedback.get("negative", 0)))
