import streamlit as st
import pandas as pd

# Função para calcular o ranking de custos
def calculate_ranking(cost_data):
    total_cost_per_scenario = {
        'Santos_DTA_Conteiner': cost_data['Santos_DTA_Conteiner'],
        'Santos_DTA_CrossDocking': cost_data['Santos_DTA_CrossDocking'],
        'Santos_DI_Conteiner': cost_data['Santos_DI_Conteiner'],
        'Santos_DDC': cost_data['Santos_DDC'],
        'Paranagua_DTA_Conteiner': cost_data['Paranagua_DTA_Conteiner'],
        'Paranagua_DTA_CrossDocking': cost_data['Paranagua_DTA_CrossDocking'],
        'Paranagua_DI_Conteiner': cost_data['Paranagua_DI_Conteiner'],
        'Paranagua_DDC': cost_data['Paranagua_DDC']
    }
    ranking = pd.DataFrame(total_cost_per_scenario.items(), columns=['Scenario', 'Total_Cost']).sort_values(by='Total_Cost')
    return ranking

# Streamlit Interface
st.title("Ferramenta de Análise de Cenários de Importação")

st.write("Preencha os dados abaixo para calcular o melhor cenário de importação.")

# Inputs manuais
data = {
    'Santos_DTA_Conteiner': st.number_input('Santos - DTA Contêiner', min_value=0, value=0),
    'Santos_DTA_CrossDocking': st.number_input('Santos - DTA Cross-Docking', min_value=0, value=0),
    'Santos_DI_Conteiner': st.number_input('Santos - DI Contêiner', min_value=0, value=0),
    'Santos_DDC': st.number_input('Santos - DDC', min_value=0, value=0),
    'Paranagua_DTA_Conteiner': st.number_input('Paranaguá - DTA Contêiner', min_value=0, value=0),
    'Paranagua_DTA_CrossDocking': st.number_input('Paranaguá - DTA Cross-Docking', min_value=0, value=0),
    'Paranagua_DI_Conteiner': st.number_input('Paranaguá - DI Contêiner', min_value=0, value=0),
    'Paranagua_DDC': st.number_input('Paranaguá - DDC', min_value=0, value=0)
}

if st.button("Calcular Melhor Cenário"):
    # Calcular o ranking
    ranking = calculate_ranking(data)
    st.write("### Ranking de Custos por Cenário de Importação:")
    st.dataframe(ranking)
    st.write("O melhor cenário está no topo do ranking.")


