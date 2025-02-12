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

# Função para calcular o custo total por cenário de forma dinâmica
def calculate_total_cost(data_dict, scenario):
    # Aplica ICMS para cenários que contenham "DI" ou "DDC" no nome
    icms_rate = 0.18 if "DI" in scenario or "DDC" in scenario else 0.0
    custo_icms = data_dict.get('Valor CIF', 0) * icms_rate
    # Soma Valor CIF + todos os demais itens (exceto "Valor CIF") + ICMS
    total_cost = data_dict.get('Valor CIF', 0) + sum(v for k, v in data_dict.items() if k != 'Valor CIF') + custo_icms
    return total_cost, custo_icms

# Título do app
st.title("DEV - Ferramenta de Análise de Cenários de Importação")

# Menu lateral com as opções do sistema
option = st.sidebar.selectbox("Escolha uma opção", 
                              ["Gerenciamento", "Configuração", "Simulador de Cenários"])

# Carrega os dados da base (JSON)
data = load_data()

# --- Área de Gerenciamento ---
if option == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo"])
    
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
                    st.info("Recarregue a página para ver as alterações.")
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
                        st.info("Recarregue a página para ver as alterações.")
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
                            st.info("Recarregue a página para ver as alterações.")
            else:
                st.info("Nenhum cenário cadastrado para essa filial.")
            
            new_scenario = st.text_input("Novo Cenário", key="new_scenario_input")
            if st.button("Adicionar Cenário"):
                new_scenario_stripped = new_scenario.strip()
                if new_scenario_stripped:
                    if new_scenario_stripped in data[filial_select]:
                        st.warning("Cenário já existe para essa filial!")
                    else:
                        # Ao adicionar um novo cenário, iniciamos com uma estrutura padrão
                        data[filial_select][new_scenario_stripped] = {
                            "Frete rodoviário": 0,
                            "Armazenagem": 0,
                            "Taxa MAPA": 0,
                            "Taxas Porto Seco": 0,
                            "Desova EAD": 0,
                            "Taxa cross docking": 0,
                            "Taxa DDC": 0
                        }
                        save_data(data)
                        st.success("Cenário adicionado com sucesso!")
                        st.info("Recarregue a página para ver as alterações.")
                else:
                    st.warning("Digite um nome válido para o cenário.")
    
    # --- Gerenciamento de Campos de Custo ---
    with management_tabs[2]:
        st.subheader("Gerenciamento de Campos de Custo")
        if not data:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial primeiro.")
        else:
            filial_for_field = st.selectbox("Selecione a Filial", list(data.keys()), key="select_filial_for_field")
            if not data[filial_for_field]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione um cenário primeiro.")
            else:
                scenario_for_field = st.selectbox("Selecione o Cenário", list(data[filial_for_field].keys()), key="select_scenario_for_field")
                scenario_fields = data[filial_for_field][scenario_for_field]
                st.markdown("### Campos existentes:")
                if scenario_fields:
                    for field in list(scenario_fields.keys()):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(field)
                        with col2:
                            if st.button("Remover", key="remove_field_" + filial_for_field + "_" + scenario_for_field + "_" + field):
                                del data[filial_for_field][scenario_for_field][field]
                                save_data(data)
                                st.success(f"Campo '{field}' removido do cenário '{scenario_for_field}' na filial '{filial_for_field}'.")
                                st.info("Recarregue a página para ver as alterações.")
                else:
                    st.info("Nenhum campo definido para este cenário.")
                new_field = st.text_input("Novo Campo", key="new_field_input")
                if st.button("Adicionar Campo"):
                    new_field_stripped = new_field.strip()
                    if new_field_stripped:
                        if new_field_stripped in scenario_fields:
                            st.warning("Campo já existe nesse cenário!")
                        else:
                            data[filial_for_field][scenario_for_field][new_field_stripped] = 0
                            save_data(data)
                            st.success("Campo adicionado com sucesso!")
                            st.info("Recarregue a página para ver as alterações.")
                    else:
                        st.warning("Digite um nome válido para o campo.")

# --- Área de Configuração ---
elif option == "Configuração":
    st.header("Configuração de Base de Custos por Filial")
    if not data:
        st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
    else:
        # Usamos um threshold para decidir entre tabs ou selectbox para escolher o cenário
        scenario_threshold = 5
        for filial in data.keys():
            st.subheader(f"Configuração de Custos - Filial: {filial}")
            if not data[filial]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione na aba Gerenciamento.")
            else:
                scenario_names = list(data[filial].keys())
                if len(scenario_names) <= scenario_threshold:
                    scenario_tabs = st.tabs(scenario_names)
                    for scenario, scenario_tab in zip(scenario_names, scenario_tabs):
                        with scenario_tab:
                            st.subheader(f"{scenario} - {filial}")
                            # Exibe os campos configurados para o cenário dinamicamente
                            if data[filial][scenario]:
                                for field, value in data[filial][scenario].items():
                                    unique_key = f"{filial}_{scenario}_{field}"
                                    updated_value = st.number_input(f"{field}", min_value=0, value=value, key=unique_key)
                                    if updated_value != value:
                                        data[filial][scenario][field] = updated_value
                                        save_data(data)
                            else:
                                st.info("Nenhum campo definido para este cenário. Adicione na aba Gerenciamento -> Campos de Custo.")
                else:
                    # Se houver muitos cenários, usa selectbox para evitar problemas de visualização das abas
                    selected_scenario = st.selectbox(f"Selecione o cenário para {filial}", scenario_names, key=f"selectbox_{filial}")
                    st.subheader(f"{selected_scenario} - {filial}")
                    if data[filial][selected_scenario]:
                        for field, value in data[filial][selected_scenario].items():
                            unique_key = f"{filial}_{selected_scenario}_{field}"
                            updated_value = st.number_input(f"{field}", min_value=0, value=value, key=unique_key)
                            if updated_value != value:
                                data[filial][selected_scenario][field] = updated_value
                                save_data(data)
                    else:
                        st.info("Nenhum campo definido para este cenário. Adicione na aba Gerenciamento -> Campos de Custo.")
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
                # Considera apenas cenários que tenham pelo menos um campo com valor > 0
                if not any(v > 0 for v in fields.values()):
                    continue

                scenario_data = fields.copy()
                scenario_data['Valor CIF'] = valor_cif
                total_cost, custo_icms = calculate_total_cost(scenario_data, scenario)
                costs[scenario] = {
                    "Custo Total": total_cost,
                    "ICMS (Calculado)": custo_icms,
                }
                # Inclui os valores individuais de cada campo
                costs[scenario].update(fields)
        
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
