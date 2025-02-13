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

# Função de cálculo do custo total usando a nova estrutura para campos
def calculate_total_cost_extended(config, base_values, taxa_cambio):
    """
    config: dicionário de campos do cenário.
    base_values: dicionário com as bases de cálculo, ex.: {"Valor CIF": valor_cif, "Valor FOB": valor_fob_usd, ...}
    taxa_cambio: taxa de câmbio (USD -> BRL) para converter as bases que estiverem em USD.
    """
    extra = 0
    for field, conf in config.items():
        if not isinstance(conf, dict):
            extra += conf
        else:
            if conf.get("type") == "fixed":
                extra += conf.get("value", 0)
            elif conf.get("type") == "percentage":
                base = conf.get("base")
                rate = conf.get("rate", 0)
                base_val = base_values.get(base, 0)
                # Converte a base se for "Valor FOB" ou "Frete Internacional"
                if base.lower() in ["valor fob", "frete internacional"]:
                    base_val = base_val * taxa_cambio
                extra += base_val * rate
    return base_values.get("Valor CIF", 0) + extra

# Função para gerar CSV com os resultados da simulação
def generate_csv(sim_record):
    results = sim_record["results"]
    df = pd.DataFrame(results).T
    csv_data = df.to_csv(index=True)
    return csv_data.encode('utf-8')

st.title("Ferramenta de Análise de Cenários de Importação")

# ----- Mecanismo de Seleção de Módulo na Sidebar com Botões -----
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

module_selected = st.session_state.module
st.sidebar.markdown(f"### Módulo Atual: **{module_selected}**")
# ----------------------------------------------------------------------

# Carrega a base de dados
data = load_data()

# ----- Área de Gerenciamento -----
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
                            "ICMS": 0,
                            "IPI": 0,
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
    
    # Gerenciamento de Campos de Custo – Definição completa do campo
    with management_tabs[2]:
        st.subheader("Gerenciamento de Campos de Custo")
        if not data:
            st.warning("Nenhuma filial cadastrada. Adicione uma filial primeiro.")
        else:
            filial_for_field = st.selectbox("Selecione a Filial", list(data.keys()), key="gerenciamento_filial")
            if not data[filial_for_field]:
                st.info("Nenhum cenário cadastrado para essa filial. Adicione um cenário primeiro.")
            else:
                scenario_for_field = st.selectbox("Selecione o Cenário", list(data[filial_for_field].keys()), key="gerenciamento_cenario")
                scenario_fields = data[filial_for_field][scenario_for_field]
                st.markdown("### Campos Existentes:")
                if scenario_fields:
                    for field in list(scenario_fields.keys()):
                        st.write(f"**Campo:** {field}")
                        current = scenario_fields[field]
                        if isinstance(current, dict):
                            current_type = current.get("type", "fixed")
                            current_fixed = float(current.get("value", 0)) if current_type=="fixed" else 0.0
                            current_rate = float(current.get("rate", 0)) if current_type=="percentage" else 0.0
                            current_base = current.get("base", "Valor CIF") if current_type=="percentage" else "Valor CIF"
                        else:
                            current_type = "fixed"
                            current_fixed = float(current)
                            current_rate = 0.0
                            current_base = "Valor CIF"
                        colA, colB, colC = st.columns([3, 3, 3])
                        with colA:
                            novo_tipo = st.radio(f"Tipo para {field}", ["fixed", "percentage"],
                                                  index=0 if current_type=="fixed" else 1,
                                                  key=f"tipo_{filial_for_field}_{scenario_for_field}_{field}")
                        if novo_tipo == "fixed":
                            with colB:
                                novo_valor = st.number_input(f"Valor Fixo para {field}",
                                                             min_value=0.0,
                                                             value=float(current_fixed),
                                                             key=f"fixo_{filial_for_field}_{scenario_for_field}_{field}")
                            scenario_fields[field] = {"type": "fixed", "value": novo_valor}
                        else:
                            with colB:
                                nova_taxa = st.number_input(f"Taxa (%) para {field}",
                                                            min_value=0.0,
                                                            value=float(current_rate)*100.0,
                                                            step=0.1,
                                                            key=f"taxa_{filial_for_field}_{scenario_for_field}_{field}")
                            with colC:
                                nova_base = st.selectbox(f"Base para {field}",
                                                         options=["Valor CIF", "Valor FOB", "Frete Internacional"],
                                                         index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(current_base),
                                                         key=f"base_{filial_for_field}_{scenario_for_field}_{field}")
                            scenario_fields[field] = {"type": "percentage", "rate": nova_taxa/100.0, "base": nova_base}
                        if st.button("Remover", key=f"remover_{filial_for_field}_{scenario_for_field}_{field}"):
                            del scenario_fields[field]
                            save_data(data)
                            st.success(f"Campo '{field}' removido com sucesso!")
                            st.experimental_rerun()
                else:
                    st.info("Nenhum campo definido para este cenário.")
                st.markdown("### Adicionar Novo Campo")
                new_field = st.text_input("Nome do Novo Campo", key="novo_campo")
                if new_field:
                    st.markdown("Defina as opções para o novo campo:")
                    field_type = st.radio("Tipo do Campo", options=["fixed", "percentage"], key=f"tipo_novo_{new_field}")
                    if field_type == "fixed":
                        field_value = st.number_input("Valor Fixo", min_value=0.0, value=0.0, key=f"valor_novo_{new_field}")
                    else:
                        field_rate = st.number_input("Taxa (%)", min_value=0.0, value=0.0, step=0.1, key=f"taxa_novo_{new_field}")
                        base_option = st.selectbox("Base", options=["Valor CIF", "Valor FOB", "Frete Internacional"], key=f"base_novo_{new_field}")
                    if st.button("Adicionar Campo", key=f"adicionar_{new_field}"):
                        new_field_stripped = new_field.strip()
                        if new_field_stripped in scenario_fields:
                            st.warning("Campo já existe nesse cenário!")
                        else:
                            if field_type == "fixed":
                                scenario_fields[new_field_stripped] = {"type": "fixed", "value": field_value}
                            else:
                                scenario_fields[new_field_stripped] = {"type": "percentage", "rate": field_rate/100.0, "base": base_option}
                            save_data(data)
                            st.success("Campo adicionado com sucesso!")
                            st.info("Recarregue a página para ver as alterações.")

# ----- Área de Configuração (Apenas alteração dos valores dos campos do tipo fixed) -----
elif module_selected == "Configuração":
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
                        for field, conf in data[filial][scenario].items():
                            if isinstance(conf, dict) and conf.get("type") == "fixed":
                                unique_key = f"{filial}_{scenario}_{field}"
                                novo_valor = st.number_input(f"{field} (Fixo)", min_value=0.0, value=float(conf.get("value", 0)), key=unique_key)
                                if novo_valor != conf.get("value", 0):
                                    data[filial][scenario][field]["value"] = novo_valor
                                    save_data(data)
                            elif isinstance(conf, dict) and conf.get("type") == "percentage":
                                st.write(f"{field} (Percentual: {conf.get('rate',0)*100:.1f}% sobre {conf.get('base','')})")
                            else:
                                unique_key = f"{filial}_{scenario}_{field}"
                                novo_valor = st.number_input(f"{field}", min_value=0.0, value=float(conf), key=unique_key)
                                if novo_valor != conf:
                                    data[filial][scenario][field] = novo_valor
                                    save_data(data)
        st.success("Configuração atualizada e salva automaticamente!")

# ----- Área do Simulador de Cenários usando a nova estrutura para cálculo -----
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
        
        # Dicionário de bases para o cálculo percentual
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
                total_cost = calculate_total_cost_extended(config, base_values, taxa_cambio)
                costs[scenario] = {"Custo Total": total_cost}
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

# ----- Área do Histórico de Simulações com exportação para CSV -----
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
