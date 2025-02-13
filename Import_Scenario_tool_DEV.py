import streamlit as st
import pandas as pd
import json
import os
import altair as alt
from datetime import datetime
import io

# Injeção de CSS para habilitar scroll horizontal na lista de abas (caso necessário)
st.markdown(
    """
    <style>
    [role="tablist"] {
      overflow-x: auto;
      scroll-behavior: smooth;
    }
    </style>
    """, unsafe_allow_html=True)

# Arquivos para os dados e para o histórico de simulações
data_file = "cost_config.json"
history_file = "simulation_history.json"

# Funções para carregar/salvar a base de dados de custos
def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

# Funções para carregar/salvar o histórico de simulações
def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    else:
        return []

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)

# Função de cálculo do custo total para cenários que usam a nova estrutura
def calculate_total_cost_extended(config, base_values):
    # 'config' é o dicionário de campos para o cenário (excluindo "Valor CIF" se existir)
    # 'base_values' contém os valores base, por exemplo: {"Valor CIF": valor_cif, "Valor FOB": valor_fob_usd, ...}
    extra = 0
    for field, conf in config.items():
        # Se o campo não for um dicionário, trata como fixo (compatibilidade)
        if not isinstance(conf, dict):
            extra += conf
        else:
            if conf.get("type") == "fixed":
                extra += conf.get("value", 0)
            elif conf.get("type") == "percentage":
                base = conf.get("base")
                rate = conf.get("rate", 0)
                extra += base_values.get(base, 0) * rate
    # Pode decidir se o valor CIF já deve ser incluído na soma – neste exemplo, vamos somá-lo.
    return base_values.get("Valor CIF", 0) + extra

# Função para gerar CSV com os resultados da simulação
def generate_csv(sim_record):
    results = sim_record["results"]
    df = pd.DataFrame(results).T  # Transpõe para melhor visualização
    csv_data = df.to_csv(index=True)
    return csv_data.encode('utf-8')

st.title("DEV - Ferramenta de Análise de Cenários de Importação")

# ----- Novo Mecanismo de Seleção de Módulo na Sidebar -----
# Define o módulo padrão se ainda não estiver definido
if 'module' not in st.session_state:
    st.session_state.module = "Simulador de Cenários"

st.sidebar.markdown("### Selecione o Módulo:")
if st.sidebar.button("Simulador de Cenários"):
    st.session_state.module = "Simulador de Cenários"
if st.sidebar.button("Gerenciamento"):
    st.session_state.module = "Gerenciamento"
if st.sidebar.button("Configuração"):
    st.session_state.module = "Configuração"
if st.sidebar.button("Histórico de Simulações"):
    st.session_state.module = "Histórico de Simulações"

# O módulo selecionado é aquele armazenado no session_state
module_selected = st.session_state.module

# --------------------------------------------------------------

# Carrega a base de dados
data = load_data()

# ----- Blocos de Módulos -----
if module_selected == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo"])
    
    # Gerenciamento de Filiais
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
    
    # Gerenciamento de Cenários
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
    
    # Gerenciamento de Campos de Custo
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

# ----- Área de Configuração com novos inputs para tipo de campo -----
elif module_selected == "Configuração":
    st.header("Configuração de Base de Custos por Filial")
    BASE_OPTIONS = ["Valor CIF", "Valor FOB", "Frete Internacional"]
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
                        # Para cada campo, permite definir se o custo é fixo ou percentual
                        for field, value in data[filial][scenario].items():
                            # Se o valor já for um dict, extraia os dados; senão, use "fixed" como padrão.
                            if isinstance(value, dict):
                                current_type = value.get("type", "fixed")
                                current_fixed = value.get("value", 0) if current_type == "fixed" else 0
                                current_rate = value.get("rate", 0) if current_type == "percentage" else 0
                                current_base = value.get("base", BASE_OPTIONS[0]) if current_type == "percentage" else BASE_OPTIONS[0]
                            else:
                                current_type = "fixed"
                                current_fixed = value
                                current_rate = 0
                                current_base = BASE_OPTIONS[0]
                            colA, colB = st.columns([2, 2])
                            with colA:
                                tipo = st.radio(f"Tipo para {field}", options=["fixed", "percentage"],
                                                index=0 if current_type=="fixed" else 1,
                                                key=f"tipo_{filial}_{scenario}_{field}")
                            if tipo == "fixed":
                                novo_valor = st.number_input(f"Valor Fixo para {field}",
                                                             min_value=0.0,
                                                             value=current_fixed,
                                                             key=f"fixo_{filial}_{scenario}_{field}")
                                data[filial][scenario][field] = {"type": "fixed", "value": novo_valor}
                            else:
                                # Para percentual, o usuário insere a taxa (em %) e escolhe a base
                                nova_taxa = st.number_input(f"Taxa (%) para {field}",
                                                            min_value=0.0,
                                                            value=current_rate * 100,
                                                            step=0.1,
                                                            key=f"taxa_{filial}_{scenario}_{field}")
                                nova_base = st.selectbox(f"Base para {field}",
                                                         options=BASE_OPTIONS,
                                                         index=BASE_OPTIONS.index(current_base) if current_base in BASE_OPTIONS else 0,
                                                         key=f"base_{filial}_{scenario}_{field}")
                                data[filial][scenario][field] = {"type": "percentage", "rate": nova_taxa/100.0, "base": nova_base}
        save_data(data)
        st.success("Configuração atualizada e salva automaticamente!")


# ----- Área do Simulador de Cenários com cálculo usando a nova estrutura -----
elif module_selected == "Simulador de Cenários":
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
        valor_cif = (valor_fob_usd + frete_internacional_usd) * taxa_cambio + taxas_frete_brl
        st.write(f"### Valor CIF Calculado: R$ {valor_cif:,.2f}")
        
        # Campo para informar o nome do processo
        processo_nome = st.text_input("Nome do Processo", key="nome_processo_input")
        
  # Monte um dicionário de bases para os cálculos percentuais:
        base_values = {
            "Valor CIF": valor_cif,
            "Valor FOB": valor_fob_usd,
            "Frete Internacional": frete_internacional_usd
        }
        
        costs = {}
        if filial_selected in data:
            for scenario, config in data[filial_selected].items():
                if scenario.lower() == "teste":
                    continue
                # Verifica se pelo menos um campo tem valor > 0 (após conversão, se for percentual)
                tem_valor = False
                for field, conf in config.items():
                    if isinstance(conf, dict):
                        if conf.get("type") == "fixed" and conf.get("value", 0) > 0:
                            tem_valor = True
                        elif conf.get("type") == "percentage" and base_values.get(conf.get("base"), 0) * conf.get("rate", 0) > 0:
                            tem_valor = True
                    elif conf > 0:
                        tem_valor = True
                if not tem_valor:
                    continue
                total_cost = calculate_total_cost_extended(config, base_values)
                costs[scenario] = {"Custo Total": total_cost}
                # Para detalhamento, calcula o valor de cada campo:
                for field, conf in config.items():
                    if isinstance(conf, dict):
                        if conf.get("type") == "fixed":
                            field_val = conf.get("value", 0)
                        elif conf.get("type") == "percentage":
                            field_val = base_values.get(conf.get("base"), 0) * conf.get("rate", 0)
                        else:
                            field_val = conf
                    else:
                        field_val = conf
                    costs[scenario][field] = field_val
        if costs:
            st.write("### Comparação de Cenários para a Filial Selecionada")
            df = pd.DataFrame(costs).T.sort_values(by="Custo Total")
            st.dataframe(df)
            chart_data = df.reset_index().rename(columns={'index': 'Cenário'})
            chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Custo Total:Q', title='Custo Total (R$)'),
                y=alt.Y('Cenário:N', title='Cenário', sort='-x'),
                tooltip=['Cenário', 'Custo Total']
            ).properties(title="Comparativo de Custos por Cenário", width=700, height=400)
            st.altair_chart(chart, use_container_width=True)
            best_scenario = df.index[0]
            best_cost = df.iloc[0]['Custo Total']
            st.write(f"O melhor cenário para {filial_selected} é **{best_scenario}** com custo total de **R$ {best_cost:,.2f}**.")
            if st.button("Salvar Simulação no Histórico"):
                history = load_history()
                simulation_record = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processo_nome": processo_nome,
                    "filial": filial_selected,
                    "valor_fob_usd": valor_fob_usd,
                    "frete_internacional_usd": frete_internacional_usd,
                    "taxas_frete_brl": taxas_frete_brl,
                    "taxa_cambio": taxa_cambio,
                    "valor_cif": valor_cif,
                    "best_scenario": best_scenario,
                    "best_cost": best_cost,
                    "results": costs
                }
                history.append(simulation_record)
                save_history(history)
                st.success("Simulação salva no histórico com sucesso!")
        else:
            st.warning("Nenhuma configuração encontrada para a filial selecionada. Por favor, configure a base de custos na aba Configuração.")
            
# ----- Área do Histórico de Simulações (mantida com exportação simples para CSV) -----
elif module_selected == "Histórico de Simulações":
    st.header("Histórico de Simulações")
    history = load_history()
    if history:
        df_history = pd.DataFrame(history)
        df_history["timestamp"] = pd.to_datetime(df_history["timestamp"], format="%Y-%m-%d %H:%M:%S")
        df_history = df_history.sort_values("timestamp", ascending=False)
        st.markdown("### Registros de Simulação")
        for i, record in df_history.iterrows():
            expander_title = (
                f"{record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | Filial: {record['filial']} | "
                f"Processo: {record.get('processo_nome', 'N/A')} | "
                f"Melhor: {record['best_scenario']} | Custo: R$ {record['best_cost']:,.2f}"
            )
            with st.expander(expander_title):
                st.markdown("**Parâmetros de Entrada:**")
                st.write(f"- **Valor FOB (USD):** {record['valor_fob_usd']}")
                st.write(f"- **Frete Internacional (USD):** {record['frete_internacional_usd']}")
                st.write(f"- **Taxas do Frete (BRL):** {record['taxas_frete_brl']}")
                st.write(f"- **Taxa de Câmbio:** {record['taxa_cambio']}")
                st.write(f"- **Valor CIF Calculado:** {record['valor_cif']}")
                st.markdown("**Resultados da Simulação:**")
                st.write(f"- **Melhor Cenário:** {record['best_scenario']}")
                st.write(f"- **Custo Total:** R$ {record['best_cost']:,.2f}")
                st.markdown("**Resultados Completos:**")
                results_df = pd.DataFrame(record["results"]).T
                st.dataframe(results_df)
                csv_bytes = generate_csv(record)
                file_name = f"{record.get('processo_nome', 'Simulacao')}_{record['timestamp'].strftime('%Y%m%d_%H%M%S')}.csv"
                st.download_button("Exportar Resultados para CSV", data=csv_bytes, file_name=file_name, mime="text/csv")
        if st.button("Limpar Histórico"):
            if st.checkbox("Confirme a limpeza do histórico"):
                save_history([])
                st.success("Histórico limpo com sucesso!")
                st.experimental_rerun()
    else:
        st.info("Nenhuma simulação registrada no histórico.")
