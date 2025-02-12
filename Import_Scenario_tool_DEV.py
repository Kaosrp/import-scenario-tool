import streamlit as st
import pandas as pd
import json
import os
import altair as alt

# Arquivo para salvar e carregar a base de dados
data_file = "cost_config.json"

def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

# Campos padrão de configuração
default_fields = ["Frete rodoviário", "Armazenagem", "Taxa MAPA", 
                  "Taxas Porto Seco", "Desova EAD", "Taxa cross docking", "Taxa DDC"]

# Função para calcular o custo total por cenário
def calculate_total_cost(data, scenario):
    # Aplica ICMS para cenários que contenham "DI" ou "DDC" no nome
    icms_rate = 0.18 if "DI" in scenario or "DDC" in scenario else 0.0
    custo_icms = data.get('Valor CIF', 0) * icms_rate
    total_cost = data.get('Valor CIF', 0) \
                 + data.get('Frete rodoviário', 0) \
                 + data.get('Armazenagem', 0) \
                 + data.get('Taxa MAPA', 0) \
                 + data.get('Taxas Porto Seco', 0) \
                 + data.get('Desova EAD', 0) \
                 + data.get('Taxa cross docking', 0) \
                 + data.get('Taxa DDC', 0) \
                 + custo_icms
    return total_cost, custo_icms

# Título do app
st.title("dev-Ferramenta de Análise de Cenários de Importação")

# Menu lateral com as opções do sistema
option = st.sidebar.selectbox("Escolha uma opção", 
                              ["Gerenciamento", "Configuração", "Simulador de Cenários"])

# Carrega os dados da base (JSON)
data = load_data()

# --- Área de Gerenciamento ---
if option == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários"])
    
    # --- Gerenciamento de Filiais ---
    with management_tabs[0]:
        st.subheader("Gerenciamento de Filiais")
        new_filial = st.text_input("Nova Filial", key="new_filial_input")
        if st.button("Adicionar Filial"):
            new_filial_stripped = new_filial.strip()
            if new_filial_stripped:
                if new_filial_stripped in data:
                    st.warning("Filial já existe!")
                else:
                    data[new_filial_stripped] = {}
                    save_data(data)
                    st.success("Filial adicionada com sucesso!")
                    st.info("Por favor, recarregue a página para ver as alterações.")
            else:
                st.warning("Digite um nome válido para a filial.")
        
        st.markdown("### Filiais existentes:")
        if data:
            for filial in list(data.keys()):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(filial)
                with col2:
                    if st.button("Excluir", key="delete_filial_" + filial):
                        del data[filial]
                        save_data(data)
                        st.success(f"Filial '{filial}' excluída.")
                        st.info("Por favor, recarregue a página para ver as alterações.")
        else:
            st.info("Nenhuma filial cadastrada.")

    # --- Gerenciamento de Cenários ---
    with management_tabs[1]:
        st.subheader("Gerenciamento de Cenários")
        if not data:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial na aba Filiais!")
        else:
            filial_select = st.selectbox("Selecione a Filial", list(data.keys()), key="select_filial_for_scenario")
            scenarios_list = list(data[filial_select].keys())
            st.markdown("### Cenários existentes:")
            if scenarios_list:
                for scenario in scenarios_list:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(scenario)
                    with col2:
                        if st.button("Excluir", key="delete_scenario_" + filial_select + "_" + scenario):
                            del data[filial_select][scenario]
                            save_data(data)
                            st.success(f"Cenário '{scenario}' excluído da filial '{filial_select}'.")
                            st.info("Por favor, recarregue a página para ver as alterações.")
            else:
                st.info("Nenhum cenário cadastrado para essa filial.")
            
            new_scenario = st.text_input("Novo Cenário", key="new_scenario_input")
            if st.button("Adicionar Cenário"):
                new_scenario_stripped = new_scenario.strip()
                if new_scenario_stripped:
                    if new_scenario_stripped in data[filial_select]:
                        st.warning("Cenário já existe para essa filial!")
                    else:
                        # Cria cenário com os campos padrão com valor 0
                        data[filial_select][new_scenario_stripped] = { field: 0 for field in default_fields }
                        save_data(data)
                        st.success("Cenário adicionado com sucesso!")
                        st.info("Por favor, recarregue a página para ver as alterações.")
                else:
                    st.warning("Digite um nome válido para o cenário.")

# --- Área de Configuração ---
elif option == "Configuração":
    st.header("Configuração de Base de Custos por Filial")
    if not data:
        st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
    else:
        for filial in data.keys():
            st.subheader(f"Configuração de Custos - Filial: {filial}")
            if not data[filial]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione na aba Gerenciamento.")
            else:
                scenario_names = list(data[filial].keys())
                scenario_tabs = st.tabs(scenario_names)
                for scenario, scenario_tab in zip(scenario_names, scenario_tabs):
                    with scenario_tab:
                        st.subheader(f"{scenario} - {filial}")
                        for field in default_fields:
                            if field not in data[filial][scenario]:
                                data[filial][scenario][field] = 0
                            current_value = data[filial][scenario][field]
                            unique_key = f"{filial}_{scenario}_{field}"
                            updated_value = st.number_input(f"{field}", min_value=0, value=current_value, key=unique_key)
                            if updated_value != current_value:
                                data[filial][scenario][field] = updated_value
                                save_data(data)
        st.success("Configuração atualizada e salva automaticamente!")

# --- Área do Simulador de Cenários ---
elif option == "Simulador de Cenários":
    st.header("Simulador de Cenários de Importação")
    if not data:
        st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
    else:
        filial_selected = st.selectbox("Selecione a Filial", list(data.keys()))
        st.subheader("Cálculo do Valor CIF")
        col1, col2 = st.columns(2)
        with col1:
            valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
            frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
        with col2:
            taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
            taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)
        
        # Cálculo do valor CIF
        valor_cif = (valor_fob_usd + frete_internacional_usd) * taxa_cambio + taxas_frete_brl
        st.write(f"### Valor CIF Calculado: R$ {valor_cif:,.2f}")
        
        costs = {}
        if filial_selected in data:
            for scenario, fields in data[filial_selected].items():
                # Ignora cenário "teste" (case insensitive)
                if scenario.lower() == "teste":
                    continue
                # Considera apenas cenários com ao menos um valor > 0 nos campos de configuração
                if all(fields.get(campo, 0) == 0 for campo in default_fields):
                    continue

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
            st.write("### Comparação de Cenários para a Filial Selecionada")
            df = pd.DataFrame(costs).T.sort_values(by="Custo Total")
            st.dataframe(df)
            # Gráfico comparativo utilizando Altair
            chart_data = df.reset_index().rename(columns={'index': 'Cenário'})
            chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Custo Total:Q', title='Custo Total (R$)'),
                y=alt.Y('Cenário:N', title='Cenário', sort='-x'),
                tooltip=['Cenário', 'Custo Total', 'ICMS (Calculado)']
            ).properties(title="Comparativo de Custos por Cenário")
            st.altair_chart(chart, use_container_width=True)
            
            st.write(f"O melhor cenário para {filial_selected} é **{df.index[0]}** com custo total de **R$ {df.iloc[0]['Custo Total']:,.2f}**.")
        else:
            st.warning("Nenhuma configuração encontrada para a filial selecionada. Por favor, configure a base de custos na aba Configuração.")
