import streamlit as st
import pandas as pd

# Função para calcular o custo total por cenário
def calculate_total_cost(data, scenario):
    icms_rate = 0.18 if "DI" in scenario or "DDC" in scenario else 0.0
    custo_icms = data.get('Valor CIF', 0) * icms_rate
    total_cost = data.get('Valor CIF', 0) + data.get('Frete rodoviário', 0) + data.get('Armazenagem', 0) + data.get('Taxa MAPA', 0)
    total_cost += data.get('Taxas Porto Seco', 0) + data.get('Desova EAD', 0) + data.get('Taxa cross docking', 0) + data.get('Taxa DDC', 0) + custo_icms
    return total_cost, custo_icms

# Streamlit Interface
st.title("Ferramenta de Análise de Cenários de Importação")

st.write("Preencha os dados para cada cenário de importação e calcule o melhor custo total.")

scenarios = {
    "DTA Contêiner - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxas Porto Seco", "Desova EAD"],
    "DTA Cross Docking - Santos": ["Valor CIF", "Frete rodoviário", "Taxa MAPA", "Taxa cross docking", "Taxas Porto Seco", "Desova EAD"],
    "DI Contêiner - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA"],
    "DDC - Santos": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxa DDC"],
    "DTA Contêiner - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxas Porto Seco", "Desova EAD"],
    "DTA Cross Docking - Paranaguá": ["Valor CIF", "Frete rodoviário", "Taxa MAPA", "Taxa cross docking", "Taxas Porto Seco", "Desova EAD"],
    "DI Contêiner - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA"],
    "DDC - Paranaguá": ["Valor CIF", "Frete rodoviário", "Armazenagem", "Taxa MAPA", "Taxa DDC"]
}

costs = {}
for scenario, fields in scenarios.items():
    st.subheader(scenario)
    data = {}
    for field in fields:
        data[field] = st.number_input(f"{field} ({scenario})", min_value=0, value=0)
    total_cost, custo_icms = calculate_total_cost(data, scenario)
    st.write(f"**Custo total para {scenario}: R$ {total_cost:,.2f}**")
    if custo_icms > 0:
        st.write(f"(Inclui ICMS de R$ {custo_icms:,.2f})")
    costs[scenario] = total_cost

if st.button("Calcular Melhor Cenário"):
    ranking = pd.DataFrame(costs.items(), columns=['Scenario', 'Total_Cost']).sort_values(by='Total_Cost')
    st.write("### Ranking de Custos por Cenário de Importação:")
    st.dataframe(ranking)
    st.write("O melhor cenário está no topo do ranking.")


