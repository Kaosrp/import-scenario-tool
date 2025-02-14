import streamlit as st
import pandas as pd
import json
import os
import altair as alt
from datetime import datetime
import io

# Função para formatar números no padrão "1.234,56"
def format_brl(x):
    try:
        s = "{:,.2f}".format(float(x))
        s = s.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return s
    except:
        return x

# Injeção de CSS para habilitar scroll horizontal na lista de abas (caso necessário)
st.markdown(
    """
    <style>
    [role="tablist"] {
      overflow-x: auto;
      scroll-behavior: smooth;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Arquivos para os dados e para o histórico de simulações
data_file = "cost_config.json"
history_file = "simulation_history.json"

def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    else:
        return {}

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)

def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    else:
        return []

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f, indent=4)

def calculate_total_cost_extended(config, base_values, taxa_cambio, occupancy_fraction):
    """
    config: dicionário de campos do cenário.
    base_values: ex.: {"Valor CIF": valor_cif_final, "Valor FOB": valor_fob, "Frete Internacional": frete_int_rateado}
    taxa_cambio: taxa de câmbio (USD -> BRL).
    occupancy_fraction: fração de ocupação do contêiner (ex.: 0.5 para 50%).
    """
    extra = 0
    for field, conf in config.items():
        if not isinstance(conf, dict):
            cost_value = conf
        else:
            field_type = conf.get("type", "fixed")
            rate_by_occupancy = conf.get("rate_by_occupancy", False)
            if field_type == "fixed":
                cost_value = conf.get("value", 0)
            elif field_type == "percentage":
                base = conf.get("base", "")
                rate = conf.get("rate", 0)
                base_val = base_values.get(base, 0)
                if base.strip().lower() in ["valor fob", "frete internacional"]:
                    base_val = base_val * taxa_cambio
                cost_value = base_val * rate
            else:
                cost_value = 0

            if rate_by_occupancy:
                cost_value *= occupancy_fraction
        
        extra += cost_value
    
    return base_values.get("Valor CIF", 0) + extra

def generate_csv(sim_record):
    results = sim_record["results"]
    df = pd.DataFrame(results).T
    df_formatted = df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
    csv_data = df_formatted.to_csv(index=True, sep=";")
    return csv_data.encode('utf-8')

st.title("Ferramenta de Análise de Cenários de Importação")

if 'module' not in st.session_state:
    st.session_state.module = "Simulador de Cenários"

st.sidebar.markdown("### Selecione o Módulo:")
if st.sidebar.button("Simulador de Cenários"):
    st.session_state.module = "Simulador de Cenários"
if st.sidebar.button("Gerenciamento"):
    st.session_state.module = "Gerenciamento"
if st.sidebar.button("Histórico de Simulações"):
    st.session_state.module = "Histórico de Simulações"

module_selected = st.session_state.module
st.sidebar.markdown(f"### Módulo Atual: **{module_selected}**")

data = load_data()

# ---------------- MÓDULO: GERENCIAMENTO ----------------
if module_selected == "Gerenciamento":
    st.header("Gerenciamento de Configurações")
    management_tabs = st.tabs(["Filiais", "Cenários", "Campos de Custo"])

    # (1) Gerenciamento de Filiais
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

    # (2) Gerenciamento de Cenários
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

    # (3) Gerenciamento de Campos de Custo
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
                st.write("**Nome do Campo | Tipo | Valor/Taxa | Base | Ratear Ocupação? | Remover**")

                if scenario_fields:
                    for field in list(scenario_fields.keys()):
                        current = scenario_fields[field]
                        if isinstance(current, dict):
                            current_type = current.get("type", "fixed")
                            current_fixed = float(current.get("value", 0)) if current_type == "fixed" else 0.0
                            current_rate = float(current.get("rate", 0)) if current_type == "percentage" else 0.0
                            current_base = current.get("base", "Valor CIF") if current_type == "percentage" else "Valor CIF"
                            current_rate_occ = bool(current.get("rate_by_occupancy", False))
                        else:
                            current_type = "fixed"
                            current_fixed = float(current)
                            current_rate = 0.0
                            current_base = "Valor CIF"
                            current_rate_occ = False

                        col1, col2, col3, col4, col5, col6 = st.columns([2.5, 2.5, 2.5, 2.5, 2, 1.8])

                        with col1:
                            st.write(f"**{field}**")

                        with col2:
                            novo_tipo = st.selectbox("Tipo",
                                                     ["fixed", "percentage"],
                                                     index=0 if current_type=="fixed" else 1,
                                                     key=f"tipo_{filial_for_field}_{scenario_for_field}_{field}")

                        novo_config = {}
                        if novo_tipo == "fixed":
                            with col3:
                                novo_valor = st.number_input("Valor Fixo",
                                                             min_value=0.0,
                                                             value=current_fixed,
                                                             key=f"fixo_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {"type": "fixed", "value": novo_valor}
                            col4.write("")
                        else:
                            with col3:
                                nova_taxa = st.number_input("Taxa (%)",
                                                            min_value=0.0,
                                                            value=current_rate * 100,
                                                            step=0.1,
                                                            key=f"taxa_{filial_for_field}_{scenario_for_field}_{field}")
                            with col4:
                                nova_base = st.selectbox("Base",
                                                         ["Valor CIF", "Valor FOB", "Frete Internacional"],
                                                         index=["Valor CIF", "Valor FOB", "Frete Internacional"].index(current_base),
                                                         key=f"base_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config = {
                                "type": "percentage",
                                "rate": nova_taxa / 100.0,
                                "base": nova_base
                            }

                        with col5:
                            novo_rate_occ = st.checkbox("Ratear?", value=current_rate_occ,
                                                        key=f"rate_occ_{filial_for_field}_{scenario_for_field}_{field}")
                            novo_config["rate_by_occupancy"] = novo_rate_occ

                        if novo_config != current:
                            scenario_fields[field] = novo_config
                            save_data(data)
                            st.success(f"Campo '{field}' atualizado com sucesso!")

                        with col6:
                            if st.button("Remover", key=f"remover_{filial_for_field}_{scenario_for_field}_{field}"):
                                del scenario_fields[field]
                                save_data(data)
                                st.success(f"Campo '{field}' removido com sucesso!")
                                st.stop()
                else:
                    st.info("Nenhum campo definido para este cenário.")

                st.markdown("### Adicionar Novo Campo")
                new_field = st.text_input("Nome do Novo Campo", key="novo_campo")
                if new_field:
                    st.markdown("Defina as opções para o novo campo:")
                    field_type = st.selectbox("Tipo do Campo", ["fixed", "percentage"], key=f"tipo_novo_{new_field}")
                    if field_type == "fixed":
                        field_value = st.number_input("Valor Fixo", min_value=0.0, value=0.0, key=f"valor_novo_{new_field}")
                    else:
                        field_rate = st.number_input("Taxa (%)", min_value=0.0, value=0.0, step=0.1, key=f"taxa_novo_{new_field}")
                        base_option = st.selectbox("Base", ["Valor CIF", "Valor FOB", "Frete Internacional"], key=f"base_novo_{new_field}")
                    rate_occ_new = st.checkbox("Ratear pela Ocupação do Contêiner?", value=False, key=f"rate_occ_new_{new_field}")

                    if st.button("Adicionar Campo", key=f"adicionar_{new_field}"):
                        new_field_stripped = new_field.strip()
                        if new_field_stripped in scenario_fields:
                            st.warning("Campo já existe nesse cenário!")
                        else:
                            if field_type == "fixed":
                                scenario_fields[new_field_stripped] = {
                                    "type": "fixed",
                                    "value": field_value,
                                    "rate_by_occupancy": rate_occ_new
                                }
                            else:
                                scenario_fields[new_field_stripped] = {
                                    "type": "percentage",
                                    "rate": field_rate / 100.0,
                                    "base": base_option,
                                    "rate_by_occupancy": rate_occ_new
                                }
                            save_data(data)
                            st.success("Campo adicionado com sucesso!")
                            st.info("Recarregue a página para ver as alterações.")


# ---------------- MÓDULO: SIMULADOR DE CENÁRIOS ----------------
if module_selected == "Simulador de Cenários":
    st.header("Simulador de Cenários de Importação")

    sim_mode = st.radio("Escolha o modo de Simulação", ["Simulador Único", "Comparação Multifilial"], index=0)

    if sim_mode == "Simulador Único":
        # ----- SIMULADOR ÚNICO (como antes) -----
        if not data:
            st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
        else:
            filial_selected = st.selectbox("Selecione a Filial", list(data.keys()))
            
            st.subheader("Forma de Inserir o Valor FOB")
            modo_valor_fob = st.selectbox(
                "Como deseja informar o Valor FOB?",
                ["Valor Total", "Unitário × Quantidade"]
            )

            col1, col2 = st.columns(2)
            if modo_valor_fob == "Valor Total":
                with col1:
                    valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
                    quantidade = 1.0
                    valor_unit_fob_usd = 0.0
                with col2:
                    frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
            else:
                with col1:
                    valor_unit_fob_usd = st.number_input("Valor Unitário FOB (USD/unidade)", min_value=0.0, value=0.0)
                    quantidade = st.number_input("Quantidade", min_value=0.0, value=0.0)
                    frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
                    valor_fob_usd = valor_unit_fob_usd * quantidade
                with col2:
                    st.write(f"Valor FOB (USD) calculado: **{valor_fob_usd:,.2f}**")

            percentual_ocupacao_conteiner = st.number_input(
                "Percentual de Ocupação do Contêiner (%)",
                min_value=0.0, max_value=100.0, value=100.0
            )
            occupancy_fraction = percentual_ocupacao_conteiner / 100.0

            frete_internacional_usd_rateado = frete_internacional_usd * occupancy_fraction

            taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
            taxas_frete_brl_rateada = taxas_frete_brl * occupancy_fraction

            taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)

            valor_cif_base = (valor_fob_usd + frete_internacional_usd_rateado) * taxa_cambio
            seguro = 0.0015 * (valor_fob_usd * taxa_cambio)
            valor_cif = valor_cif_base + seguro

            st.write(f"Frete Internacional Rateado (USD): {frete_internacional_usd_rateado:,.2f}")
            st.write(f"Taxas do Frete (BRL) Rateadas: {format_brl(taxas_frete_brl_rateada)}")
            st.write(f"Seguro (0,15% do Valor FOB): R$ {format_brl(seguro)}")
            st.write(f"### Valor CIF Calculado (com Seguro): R$ {format_brl(valor_cif)}")

            processo_nome = st.text_input("Nome do Processo", key="nome_processo_input")

            base_values = {
                "Valor CIF": valor_cif,
                "Valor FOB": valor_fob_usd,
                "Frete Internacional": frete_internacional_usd_rateado
            }

            costs = {}
            if filial_selected in data:
                for scenario, config in data[filial_selected].items():
                    if scenario.lower() == "teste":
                        continue
                    tem_valor = False
                    for field, conf in config.items():
                        if isinstance(conf, dict):
                            field_type = conf.get("type", "fixed")
                            if field_type == "fixed" and conf.get("value", 0) > 0:
                                tem_valor = True
                            elif field_type == "percentage":
                                base_name = conf.get("base", "")
                                base_val = base_values.get(base_name, 0)
                                if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                                    base_val = base_val * taxa_cambio
                                if base_val * conf.get("rate", 0) > 0:
                                    tem_valor = True
                        elif conf > 0:
                            tem_valor = True
                    if not tem_valor:
                        continue

                    scenario_cost = calculate_total_cost_extended(config, base_values, taxa_cambio, occupancy_fraction)
                    final_cost = scenario_cost + taxas_frete_brl_rateada

                    costs[scenario] = {"Custo Total": final_cost}
                    if quantidade > 0:
                        costs[scenario]["Custo Unitário"] = final_cost / quantidade

                    for field, conf in config.items():
                        if isinstance(conf, dict):
                            field_type = conf.get("type", "fixed")
                            rate_by_occupancy = conf.get("rate_by_occupancy", False)
                            base_name = conf.get("base", "")
                            if field_type == "fixed":
                                field_val = conf.get("value", 0)
                            elif field_type == "percentage":
                                rate = conf.get("rate", 0)
                                base_val = base_values.get(base_name, 0)
                                if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                                    base_val = base_val * taxa_cambio
                                field_val = base_val * rate
                            else:
                                field_val = 0
                            if rate_by_occupancy:
                                field_val *= occupancy_fraction
                            costs[scenario][field] = field_val

                    costs[scenario]["Taxas Frete (BRL) Rateadas"] = taxas_frete_brl_rateada

                if costs:
                    st.write("### Comparação de Cenários para a Filial Selecionada")
                    df = pd.DataFrame(costs).T.sort_values(by="Custo Total")
                    df_display = df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                    st.dataframe(df_display)

                    chart_data = df.reset_index().rename(columns={'index': 'Cenário'})
                    chart = alt.Chart(chart_data).mark_bar().encode(
                        x=alt.X('Custo Total:Q', title='Custo Total (R$)'),
                        y=alt.Y('Cenário:N', title='Cenário', sort='-x'),
                        tooltip=['Cenário', 'Custo Total']
                    ).properties(title="Comparativo de Cenários", width=700, height=400)
                    st.altair_chart(chart, use_container_width=True)

                    best_scenario = df.index[0]
                    best_cost = df.iloc[0]['Custo Total']
                    st.write(f"O melhor cenário para {filial_selected} é **{best_scenario}** com custo total de **R$ {format_brl(best_cost)}**.")

                    if st.button("Salvar Simulação no Histórico"):
                        history = load_history()
                        simulation_record = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "processo_nome": processo_nome,
                            "filial": filial_selected,
                            "modo_valor_fob": modo_valor_fob,
                            "valor_unit_fob_usd": valor_unit_fob_usd,
                            "quantidade": float(quantidade),
                            "valor_fob_usd": valor_fob_usd,
                            "frete_internacional_usd": frete_internacional_usd,
                            "percentual_ocupacao_conteiner": percentual_ocupacao_conteiner,
                            "frete_internacional_usd_rateado": frete_internacional_usd_rateado,
                            "taxas_frete_brl": taxas_frete_brl,
                            "taxas_frete_brl_rateada": taxas_frete_brl_rateada,
                            "taxa_cambio": taxa_cambio,
                            "seguro_0_15_valor_fob": float(0.0015 * (valor_fob_usd * taxa_cambio)),
                            "valor_cif": base_values["Valor CIF"],
                            "best_scenario": best_scenario,
                            "best_cost": best_cost,
                            "results": costs
                        }
                        if quantidade > 0:
                            simulation_record["custo_unitario_melhor"] = best_cost / quantidade

                        history.append(simulation_record)
                        save_history(history)
                        st.success("Simulação salva no histórico com sucesso!")
                else:
                    st.warning("Nenhuma configuração encontrada para a filial selecionada. "
                               "Verifique se há cenários com valores > 0 ou se a base de custos está configurada.")

    else:
        # ----- COMPARAÇÃO MULTIFILIAL -----
        st.subheader("Comparação Multifilial")
        if not data:
            st.warning("Nenhuma filial cadastrada. Adicione filiais na aba Gerenciamento.")
        else:
            filiais_multi = st.multiselect("Selecione as Filiais para comparar", list(data.keys()))
            if filiais_multi:
                st.markdown("Defina os parâmetros (aplicados a todas as filiais):")

                modo_valor_fob = st.selectbox(
                    "Como deseja informar o Valor FOB?",
                    ["Valor Total", "Unitário × Quantidade"]
                )

                col1, col2 = st.columns(2)
                if modo_valor_fob == "Valor Total":
                    with col1:
                        valor_fob_usd = st.number_input("Valor FOB da Mercadoria (USD)", min_value=0.0, value=0.0)
                        quantidade = 1.0
                        valor_unit_fob_usd = 0.0
                    with col2:
                        frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
                else:
                    with col1:
                        valor_unit_fob_usd = st.number_input("Valor Unitário FOB (USD/unidade)", min_value=0.0, value=0.0)
                        quantidade = st.number_input("Quantidade", min_value=0.0, value=0.0)
                        frete_internacional_usd = st.number_input("Frete Internacional (USD)", min_value=0.0, value=0.0)
                        valor_fob_usd = valor_unit_fob_usd * quantidade
                    with col2:
                        st.write(f"Valor FOB (USD) calculado: **{valor_fob_usd:,.2f}**")

                percentual_ocupacao_conteiner = st.number_input(
                    "Percentual de Ocupação do Contêiner (%)",
                    min_value=0.0, max_value=100.0, value=100.0
                )
                occupancy_fraction = percentual_ocupacao_conteiner / 100.0

                frete_internacional_usd_rateado = frete_internacional_usd * occupancy_fraction

                taxas_frete_brl = st.number_input("Taxas do Frete (BRL)", min_value=0.0, value=0.0)
                taxas_frete_brl_rateada = taxas_frete_brl * occupancy_fraction

                taxa_cambio = st.number_input("Taxa de Câmbio (USD -> BRL)", min_value=0.0, value=5.0)

                valor_cif_base = (valor_fob_usd + frete_internacional_usd_rateado) * taxa_cambio
                seguro = 0.0015 * (valor_fob_usd * taxa_cambio)
                valor_cif = valor_cif_base + seguro

                st.write(f"Frete Internacional Rateado (USD): {frete_internacional_usd_rateado:,.2f}")
                st.write(f"Taxas do Frete (BRL) Rateadas: {format_brl(taxas_frete_brl_rateada)}")
                st.write(f"Seguro (0,15% do Valor FOB): R$ {format_brl(seguro)}")
                st.write(f"### Valor CIF Calculado (com Seguro): R$ {format_brl(valor_cif)}")

                base_values = {
                    "Valor CIF": valor_cif,
                    "Valor FOB": valor_fob_usd,
                    "Frete Internacional": frete_internacional_usd_rateado
                }

                multi_costs = {}
                for filial in filiais_multi:
                    if filial not in data:
                        continue
                    for scenario, config in data[filial].items():
                        if scenario.lower() == "teste":
                            continue
                        tem_valor = False
                        for field, conf in config.items():
                            if isinstance(conf, dict):
                                field_type = conf.get("type", "fixed")
                                if field_type == "fixed" and conf.get("value", 0) > 0:
                                    tem_valor = True
                                elif field_type == "percentage":
                                    base_name = conf.get("base", "")
                                    base_val = base_values.get(base_name, 0)
                                    if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                                        base_val = base_val * taxa_cambio
                                    if base_val * conf.get("rate", 0) > 0:
                                        tem_valor = True
                            elif conf > 0:
                                tem_valor = True
                        if not tem_valor:
                            continue

                        scenario_cost = calculate_total_cost_extended(config, base_values, taxa_cambio, occupancy_fraction)
                        final_cost = scenario_cost + taxas_frete_brl_rateada

                        multi_costs[(filial, scenario)] = {
                            "Filial": filial,
                            "Cenário": scenario,
                            "Custo Total": final_cost
                        }
                        if quantidade > 0:
                            multi_costs[(filial, scenario)]["Custo Unitário"] = final_cost / quantidade

                        for field, conf in config.items():
                            if isinstance(conf, dict):
                                field_type = conf.get("type", "fixed")
                                rate_by_occupancy = conf.get("rate_by_occupancy", False)
                                base_name = conf.get("base", "")
                                if field_type == "fixed":
                                    field_val = conf.get("value", 0)
                                elif field_type == "percentage":
                                    rate = conf.get("rate", 0)
                                    base_val = base_values.get(base_name, 0)
                                    if base_name.strip().lower() in ["valor fob", "frete internacional"]:
                                        base_val = base_val * taxa_cambio
                                    field_val = base_val * rate
                                else:
                                    field_val = 0
                                if rate_by_occupancy:
                                    field_val *= occupancy_fraction
                            else:
                                field_val = conf
                            multi_costs[(filial, scenario)][field] = field_val

                        multi_costs[(filial, scenario)]["Taxas Frete (BRL) Rateadas"] = taxas_frete_brl_rateada

                if multi_costs:
                    df_multi = pd.DataFrame(multi_costs).T
                    df_multi = df_multi.sort_values(by="Custo Total")

                    df_display = df_multi.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                    st.write("### Comparação Global (Multifilial)")
                    st.dataframe(df_display)

                    chart_data = df_multi.reset_index()
                    chart_data["Filial_Cenario"] = chart_data["Filial"] + " | " + chart_data["Cenário"]
                    chart = alt.Chart(chart_data).mark_bar().encode(
                        x=alt.X('Custo Total:Q', title='Custo Total (R$)'),
                        y=alt.Y('Filial_Cenario:N', title='Filial | Cenário', sort='-x'),
                        tooltip=['Filial_Cenario', 'Custo Total']
                    ).properties(title="Comparativo Multifilial", width=700, height=400)
                    st.altair_chart(chart, use_container_width=True)

                    best_row = df_multi.iloc[0]
                    best_filial = best_row["Filial"]
                    best_scenario = best_row["Cenário"]
                    best_cost = best_row["Custo Total"]
                    st.write(f"O melhor cenário geral é **{best_scenario}** da filial **{best_filial}** "
                             f"com custo total de **R$ {format_brl(best_cost)}**.")

                    # Botão para salvar comparação multifilial no histórico
                    if st.button("Salvar Comparação no Histórico"):
                        history = load_history()
                        # Montamos um único registro contendo todas as infos
                        # Se quiser, pode pedir um "nome do processo" também aqui
                        processo_nome_multi = st.text_input("Nome do Processo para Comparação", key="proc_multi")
                        # Para que o app não fique bloqueado esperando, pedimos acima ou assumimos algo

                        # Precisamos de st.session_state para armazenar, ou perguntamos acima. 
                        # Se quiser, adaptamos: se "Salvar" for clicado, iremos gravar com "Comparacao Multifilial" no record.
                        simulation_record = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "processo_nome": processo_nome_multi,  # ou algo fixo
                            "multi_comparison": True,
                            "filiais_multi": filiais_multi,
                            "modo_valor_fob": modo_valor_fob,
                            "valor_unit_fob_usd": valor_unit_fob_usd,
                            "quantidade": float(quantidade),
                            "valor_fob_usd": valor_fob_usd,
                            "frete_internacional_usd": frete_internacional_usd,
                            "percentual_ocupacao_conteiner": percentual_ocupacao_conteiner,
                            "frete_internacional_usd_rateado": frete_internacional_usd_rateado,
                            "taxas_frete_brl": taxas_frete_brl,
                            "taxas_frete_brl_rateada": taxas_frete_brl_rateada,
                            "taxa_cambio": taxa_cambio,
                            "seguro_0_15_valor_fob": float(0.0015 * (valor_fob_usd * taxa_cambio)),
                            "valor_cif": valor_cif,
                            "best_filial": best_filial,
                            "best_scenario": best_scenario,
                            "best_cost": best_cost,
                            "results": {}  # iremos armazenar multi_costs ou df_multi
                        }

                        # Para armazenar todos os dados de multi_costs, podemos colocar:
                        simulation_record["results"] = df_multi.to_dict(orient="index")

                        history.append(simulation_record)
                        save_history(history)
                        st.success("Comparação Multifilial salva no histórico com sucesso!")
                else:
                    st.warning("Nenhuma configuração encontrada para as filiais selecionadas. "
                               "Verifique se há cenários com valores > 0 ou se a base de custos está configurada.")
            else:
                st.info("Selecione pelo menos uma filial para comparar.")

# ---------------- MÓDULO: HISTÓRICO DE SIMULAÇÕES ----------------
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
                f"{record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            # Se for comparacao multifilial, podemos exibir um título diferente
            if record.get("multi_comparison", False):
                expander_title += " (Comparação Multifilial)"
            else:
                expander_title += f" | Filial: {record.get('filial', 'N/A')}"
                if "best_scenario" in record:
                    expander_title += f" | Melhor: {record['best_scenario']}"
                if "best_cost" in record:
                    expander_title += f" | Custo: R$ {format_brl(record['best_cost'])}"

            with st.expander(expander_title):
                st.write(f"**Processo:** {record.get('processo_nome', 'N/A')}")
                st.write(f"**Data/Hora:** {record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

                if record.get("multi_comparison", False):
                    # Exibimos dados de comparação multifilial
                    st.write("**Filiais Selecionadas:**", record.get("filiais_multi", []))
                    st.write("**Melhor Filial:**", record.get("best_filial", "N/A"))
                    st.write("**Melhor Cenário:**", record.get("best_scenario", "N/A"))
                    st.write("**Melhor Custo:** R$", format_brl(record.get("best_cost", 0.0)))
                    st.write("**Valor CIF:** R$", format_brl(record.get("valor_cif", 0.0)))
                    st.write("**Taxas Frete BRL Rateada:** R$", format_brl(record.get("taxas_frete_brl_rateada", 0.0)))
                    st.write("**Seguro (0,15% Valor FOB):** R$", format_brl(record.get("seguro_0_15_valor_fob", 0.0)))
                    # results é df_multi em to_dict(orient="index")
                    results_dict = record.get("results", {})
                    if results_dict:
                        results_df = pd.DataFrame.from_dict(results_dict, orient="index")
                        # Format
                        results_df_display = results_df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                        st.dataframe(results_df_display)
                else:
                    # Exibimos dados do simulador único
                    st.write(f"**Filial:** {record.get('filial', 'N/A')}")
                    st.write(f"**Melhor Cenário:** {record.get('best_scenario', 'N/A')}")
                    st.write(f"**Custo Total:** R$ {format_brl(record.get('best_cost', 0.0))}")
                    results_dict = record.get("results", {})
                    if results_dict:
                        results_df = pd.DataFrame(results_dict).T
                        results_df_display = results_df.applymap(lambda x: format_brl(x) if isinstance(x, (int, float)) else x)
                        st.dataframe(results_df_display)
                # Caso queira exibir mais campos, basta adicionar

        if st.button("Limpar Histórico"):
            if st.checkbox("Confirme a limpeza do histórico"):
                save_history([])
                st.success("Histórico limpo com sucesso!")
                st.experimental_rerun()
    else:
        st.info("Nenhuma simulação registrada no histórico.")
