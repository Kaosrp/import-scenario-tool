import streamlit as st
import pandas as pd
import json
import os

# Função para salvar e carregar a base de dados
data_file = "cost_config.json"
def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f)

# Função para calcular o custo total por cenário
def calculate_total_cost(data, scenario):
    icms_rate = 0.18 if "DI" in scenario or "DDC" in scenario else 0.0
    custo_icms = data.get('Valor CIF', 0) * icms_rate
    total_cost = data.get('Valor CIF', 0) + data.get('Frete rodoviário', 0) + data.get('Armazenagem', 0) + data.get('Taxa MAPA', 0)
    total_cost += data.get('Taxas Porto Seco', 0) + data.get('Desova EAD', 0) + data.get('Taxa cross docking', 0) + data.get('Taxa DDC', 0) + custo_icms
    return total_cost, custo_icms

# Interface Principal
st.title("Ferramenta de Análise de Cenários de Importação")
option = st.sidebar.selectbox("Escolha uma opção", ["Configuração", "Simulador de Cenários"])

data = load_data()

if option == "Configuração":
    st.header("Configuração de Base de Custos")
    tabs = st.tabs(["DTA Contêiner - Santos", "DTA Cross Docking - Santos", "DI Contêiner - Santos", "DDC - Santos", "DTA Contêiner - Paranaguá", "DTA Cross Docking - Paranaguá", "DI Contêiner - Paranaguá", "DDC - Paranaguá"])
    scenarios = ["DTA Contêiner - Santos", "DTA Cross Docking - Santos", "DI Contêiner - Santos", "DDC - Santos", "DTA Contêiner - Paranaguá", "DTA Cross Docking - Paranaguá", "DI Contêiner - Paranaguá", "DDC - Paranaguá"]
    for tab, scenario in zip(tabs, scenarios):
        with tab:
            st.subheader(f"Configuração para {scenario}")
            if scenario not in data:
                data[scenario] = {}
            for field in ["Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxas Porto Seco", "Desova EAD", "Taxa cross docking", "Taxa DDC"]:
                default_value = data[scenario].get(field, 0)
                data[scenario][field] = st.number_input(f"{field}", min_value=0, value=default_value, key=f"{scenario}_{field}")
    if st.button("Salvar Configuração"):
        save_data(data)
        st.success("Configuração salva com sucesso!")

elif option == "Simulador de Cenários":
    st.header("Simulador de Cenários de Importação")
    st.subheader("Cálculo do Valor CIF")
    valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
    frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
    taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
    taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)

    valor_cif = (valor_fob_usd + frete_internacional_usd) * taxa_cambio + taxas_frete_brl
    st.write(f"### Valor CIF Calculado: R$ {valor_cif:,.2f}")

    costs = {}
    for scenario, fields in data.items():
        scenario_data = fields.copy()
        scenario_data['Valor CIF'] = valor_cif
        total_cost, custo_icms = calculate_total_cost(scenario_data, scenario)
        costs[scenario] = {
            "Custo Total": total_cost,
            "ICMS (Calculado)": custo_icms,
            "Frete Rodoviário": scenario_data.get('Frete rodoviário', 0),
            "Taxa MAPA": scenario_data.get('Taxa MAPA', 0),
            "Armazenagem": scenario_data.get('Armazenagem', 0),
            "Taxas Porto Seco": scenario_data.get('Taxas Porto Seco', 0),
            "Desova EAD": scenario_data.get('Desova EAD', 0),
            "Taxa Cross Docking": scenario_data.get('Taxa cross docking', 0),
            "Taxa DDC": scenario_data.get('Taxa DDC', 0)
        }
    
    if costs:
        st.write("### Comparação de Cenários")
        df = pd.DataFrame(costs).T.sort_values(by="Custo Total")
        st.dataframe(df)
        st.write(f"O melhor cenário é **{df.index[0]}** com custo total de **R$ {df.iloc[0]['Custo Total']:,.2f}**.")
    else:
        st.warning("Nenhum cenário foi configurado ainda. Por favor, configure a base de custos na aba Configuração.")
