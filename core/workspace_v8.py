from __future__ import annotations

import json

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

    export_rows = [
        {
            "type": item.get("memory_type", "fact"),
            "content": item.get("content", ""),
            "importance": item.get("importance", 0.5),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
        for item in memories
    ]
    st.download_button(
        "Exportar minhas memórias",
        data=json.dumps(export_rows, ensure_ascii=False, indent=2),
        file_name=f"rog-ai-memorias-{profile.casefold()}.json",
        mime="application/json",
        use_container_width=True,
        help="Exporta somente o espaço de memória atualmente visível.",
    )

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
                with st.popover("Editar", use_container_width=True):
                    edited = st.text_area("Conteúdo", value=content, key=f"edit_memory_text_{memory_id[:16]}", max_chars=2000)
                    edited_importance = st.slider("Importância", 0.0, 1.0, importance, 0.05, key=f"edit_memory_importance_{memory_id[:16]}")
                    expiry = st.selectbox("Validade", ("Sem expiração", "30 dias", "90 dias", "365 dias"), key=f"edit_memory_expiry_{memory_id[:16]}")
                    days = {"30 dias": 30, "90 dias": 90, "365 dias": 365}.get(expiry)
                    if st.button("Salvar alteração", key=f"save_memory_{memory_id[:16]}", type="primary", use_container_width=True):
                        if memory_service.edit_authorized(profile, agent_id, memory_id, content=edited, importance=edited_importance, expires_in_days=days, shared_finance=shared_finance):
                            st.success("Memória atualizada.")
                            st.rerun()
                        st.error("Não foi possível atualizar essa memória.")
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
        type=["txt", "md", "csv", "json", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "webp"],
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


def render_system_view(*, cookie_ready: bool, profile: str, feedback: dict, is_admin: bool = False, auth_backend: str = "legacy", operations: dict | None = None, auth_identity=None) -> None:
    st.subheader("Sistema")
    st.caption("Diagnóstico seguro. Nenhuma chave ou credencial é exibida.")

    status = Config.status()
    rows = [
        ("NVIDIA NIM", status.get("nvidia", False), "Provider hospedado preferencial"),
        ("DeepSeek", status.get("deepseek", False), "Provider em nuvem"),
        ("Supabase", status.get("supabase", False), "Persistência remota opcional"),
        ("Supabase Auth", status.get("supabase_auth", False), f"Autenticação atual: {auth_backend}"),
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

    if is_admin:
        st.markdown("#### Acesso da família")
        st.caption("Gere uma senha temporária única. A pessoa será obrigada a escolher outra no primeiro acesso.")
        target = st.selectbox("Perfil", ("Beatriz", "Tainan"), key="admin_temp_password_profile")
        if st.button("Gerar senha temporária", key="admin_generate_temp_password", use_container_width=True):
            from core.supabase_auth import generate_temporary_password
            temporary = generate_temporary_password(auth_identity, target) if auth_identity else ""
            if temporary:
                st.session_state.generated_temporary_password = {"profile": target, "password": temporary}
            else:
                st.error("Não foi possível gerar a senha. Entre novamente como administrador e tente outra vez.")
        generated = st.session_state.get("generated_temporary_password") or {}
        if generated:
            st.success(f"Senha temporária de {generated.get('profile')} gerada. Ela será mostrada somente nesta sessão.")
            st.code(str(generated.get("password") or ""), language=None)
            if st.button("Já copiei · ocultar", key="admin_hide_temp_password"):
                st.session_state.generated_temporary_password = None
                st.rerun()

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
        remote = operations or {}
        st.markdown("#### Operação remota · últimos 7 dias")
        if remote.get("available"):
            rcols = st.columns(4)
            rcols[0].metric("Chamadas API", int(remote.get("requests", 0)))
            rcols[1].metric("Usuários ativos", int(remote.get("active_users", 0)))
            duration = remote.get("average_duration_ms")
            rcols[2].metric("Tempo médio", f"{duration} ms" if duration is not None else "Sem dados")
            rcols[3].metric("Falhas/negações", int(remote.get("denied_or_failed_events", 0)))
            if remote.get("estimated_cost") is not None:
                st.caption(f"Custo estimado registrado: {float(remote['estimated_cost']):.6f}. Só aparece quando o provider fornece dados reais de uso.")
            if remote.get("providers"):
                st.caption("Providers: " + " · ".join(f"{name}: {count}" for name, count in sorted(remote["providers"].items())))
        else:
            st.caption("Sem dados operacionais remotos disponíveis.")

