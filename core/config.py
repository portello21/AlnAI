import streamlit as st
import os

class Config:
    DEEPSEEK_API = st.secrets.get("DEEPSEEK_API_KEY")
    SUPABASE_URL = st.secrets.get("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN")
    
    @classmethod
    def validate(cls):
        if not all([cls.DEEPSEEK_API, cls.SUPABASE_URL, cls.SUPABASE_KEY]):
            raise EnvironmentError("Segredos críticos do Streamlit não configurados.")