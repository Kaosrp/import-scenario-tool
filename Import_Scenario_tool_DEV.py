import streamlit as st
import pandas as pd
import json
import os
import altair as alt
from datetime import datetime
from streamlit_option_menu import option_menu  # Menu com ícones

# Injeção de CSS para scroll horizontal em abas
st.markdown(
    """
    <style>
    [role="tablist"] {
      overflow-x: auto;
      scroll-behavior: smooth;
    }
    </style>
    """, unsafe_allow_html=True
)

# Arquivos para armazenar dados
data_file = "cost_config.json"
history_file = "simulation_history.json"

# Funções para carregar/salvar dados
def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)

# Função para cálculo de custo total e ICMS
def calculate_total_cost(data_dict, scenario):
    icms_rate = 0.18 if ("DI" in scenario or "DDC" in scenario) else 0.0
    custo_icms = data_dict.get('Valor CIF', 0) * icms_rate
    total_cost = data_dict.get('Valor CIF', 0) + sum(v for k, v in data_dict.items() if k != 'Valor CIF') + custo_icms
    return total_cost, custo_icms

# --- Interface principal ---
with st.sidebar:
    option = option_menu(
        "Menu Principal",
        ["Dashboard", "Gerenciamento", "Configuração", "Simulador de Cenários", "Histórico de Simulações"],
        icons=["bar-chart", "gear", "sliders", "calculator", "clock-history"],
        menu_icon="menu-app",
        default_index=0,
    )

data = load_data()

# --- Dashboard ---
if option == "Dashboard":
    st.title("Dashboard - Resumo de Simulações")
    history = load_history()
    if history:
        df_history = pd.DataFrame(history)
        df_history["timestamp"] = pd.to_datetime(df_history["timestamp"], format="%Y-%m-%d %H:%M:%S")
        st.subheader("Simulações Recentes")
        last_simulations = df_history.sort_values("timestamp", ascending=False).head(5)
        st.dataframe(last_simulations[["timestamp", "filial", "processo_nome", "best_scenario", "best_cost"]])
        
        st.subheader("Gráfico: Média de Custos por Cenário")
        avg_costs = df_history.groupby("best_scenario")["best_cost"].mean().reset_index()
        chart = alt.Chart(avg_costs).mark_bar().encode(
            x=alt.X("best_scenario", title="Cenário"),
            y=alt.Y("best_cost", title="Custo Médio (R$)")
        ).properties(title="Custo Médio por Cenário")
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nenhuma simulação registrada no histórico.")

# --- Gerenciamento ---
elif option == "Gerenciamento":
    st.title("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo"])
    
    with management_tabs[0]:  # Gerenciamento de Filiais
        st.subheader("Gerenciamento de Filiais")
        new_filial = st.text_input("Nova Filial")
        if st.button("Adicionar Filial"):
            new_filial_stripped = new_filial.strip()
            if new_filial_stripped:
                if new_filial_stripped in data:
                    st.warning("Filial já existe!")
                else:
                    data[new_filial_stripped] = {}
                    save_data(data)
                    st.toast("Filial adicionada com sucesso!")
            else:
                st.warning("Digite um nome válido para a filial.")

# --- Configuração ---
elif option == "Configuração":
    st.title("Configuração de Base de Custos por Filial")
    if not data:
        st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
    else:
        for filial in data.keys():
            st.subheader(f"Configuração de Custos - Filial: {filial}")
            scenario_names = list(data[filial].keys())
            for scenario in scenario_names:
                with st.form(key=f"form_{filial}_{scenario}"):
                    st.subheader(f"{scenario}")
                    for field, value in data[filial][scenario].items():
                        data[filial][scenario][field] = st.number_input(field, min_value=0, value=value)
                    submitted = st.form_submit_button("Salvar Alterações")
                    if submitted:
                        save_data(data)
                        st.toast(f"Configuração de {scenario} salva com sucesso!")

# --- Simulador de Cenários ---
elif option == "Simulador de Cenários":
    st.title("Simulador de Cenários de Importação")
    if not data:
        st.warning("Nenhuma filial cadastrada.")
    else:
        filial_selected = st.selectbox("Selecione a Filial", list(data.keys()))
        st.subheader("Cálculo do Valor CIF")
        with st.form(key="form_simulacao"):
            col1, col2 = st.columns(2)
            with col1:
                valor_fob_usd = st.number_input("Valor FOB (USD)", min_value=0.0, value=0.0)
                frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
            with col2:
                taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
                taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)
            submitted = st.form_submit_button("Calcular")
        
        if submitted:
            valor_cif = (valor_fob_usd + frete_internacional_usd) * taxa_cambio + taxas_frete_brl
            st.write(f"### Valor CIF Calculado: R$ {valor_cif:,.2f}")

# --- Histórico de Simulações ---
elif option == "Histórico de Simulações":
    st.title("Histórico de Simulações")
    history = load_history()
    if history:
        df_history = pd.DataFrame(history)
        df_history["timestamp"] = pd.to_datetime(df_history["timestamp"], format="%Y-%m-%d %H:%M:%S")
        st.dataframe(df_history.sort_values("timestamp", ascending=False))
    else:
        st.info("Nenhuma simulação registrada no histórico.")

