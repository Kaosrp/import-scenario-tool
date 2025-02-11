import streamlit as st
import pandas as pd

# Função para calcular o custo total por cenário
def calculate_total_cost(data):
    total_cost = data['Valor CIF'] + data['Frete rodoviário'] + data['Armazenagem'] + data['Taxa MAPA']
    if 'Taxas Porto Seco' in data:
        total_cost += data['Taxas Porto Seco']
    if 'Desova EAD' in data:
        total_cost += data['Desova EAD']
    if 'Taxa cross docking' in data:
        total_cost += data['Taxa cross docking']
    if 'Taxa DDC' in data:
        total_cost += data['Taxa DDC']
    if 'Custo de ICMS' in data:
        total_cost += data['Custo de ICMS']
    return total_cost

# Streamlit Interface
st.title("Ferramenta de Análise de Cenários de Importação")

st.write("Preencha os dados para cada cenário de importação e calcule o melhor custo total.")

scenarios = {
    "DTA Contêiner - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxas Porto Seco", "Desova EAD"],
    "DTA Cross Docking - Santos": ["Valor CIF", "Frete rodoviário", "Taxa MAPA", "Taxa cross docking", "Taxas Porto Seco", "Desova EAD"],
    "DI Contêiner - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Custo de ICMS"],
    "DDC - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxa DDC", "Custo de ICMS"],
    "DTA Contêiner - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxas Porto Seco", "Desova EAD"],
    "DTA Cross Docking - Paranaguá": ["Valor CIF", "Frete rodoviário", "Taxa MAPA", "Taxa cross docking", "Taxas Porto Seco", "Desova EAD"],
    "DI Contêiner - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Custo de ICMS"],
    "DDC - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxa DDC", "Custo de ICMS"]
}

costs = {}
for scenario, fields in scenarios.items():
    st.subheader(scenario)
    data = {}
    for field in fields:
        default_value = 0 if field != "Custo de ICMS" else (18 if "Custo de ICMS" in fields else 0)
        data[field] = st.number_input(f"{field} ({scenario})", min_value=0, value=default_value)
    total_cost = calculate_total_cost(data)
    st.write(f"**Custo total para {scenario}: R$ {total_cost:,.2f}**")
    costs[scenario] = total_cost

if st.button("Calcular Melhor Cenário"):
    ranking = pd.DataFrame(costs.items(), columns=['Scenario', 'Total_Cost']).sort_values(by='Total_Cost')
    st.write("### Ranking de Custos por Cenário de Importação:")
    st.dataframe(ranking)
    st.write("O melhor cenário está no topo do ranking.")

