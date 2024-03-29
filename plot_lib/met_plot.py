# -*- coding: utf-8 -*-
"""
Created on Wed Jan 27, 2022

SHREAD Dash Meteorology Plot

Script for running the meteorology plot in the dashboard (shread_dash.py)

@author: buriona, tclarkin (2020-2022)

"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

from database import snotel_sites
from database import csas_gages

from plot_lib.utils import import_snotel,import_csas_live
from plot_lib.utils import screen_spatial,ba_stats_std,screen_csas,screen_snotel
from plot_lib.utils import ba_mean_plot
from plot_lib.utils import shade_forecast

def get_met_plot(basin, elrange, aspects, slopes, start_date,
                 end_date, snotel_sel, csas_sel, plot_albedo, dtype,
                 forecast_sel,offline=True):
    """
    :description: this function updates the meteorology plot
    :param basin: the selected basins (checklist)
    :param elrange: the range of elevations ([min,max])
    :param aspects: the range of aspects  ([min,max])
    :param slopes: the range of slopes ([min,max])
    :param start_date: start date (from date selector)
    :param end_date: end date (from date selector)
    :param snotel_sel: list of selected snotel sites ([])
    :param csas_sel: list of selected csas sites ([])
    :param plot_albedo: boolean, plot albedo data for selected csas_sel
    :param dtype: data type (dv/iv)
    :return: update figure
    """

   # Create date axis
    dates = pd.date_range(start_date, end_date, freq="D", tz='UTC')
    freeze = 32

    if len(forecast_sel)>0:
        plot_forecast=True
    else:
        plot_forecast=False

    ## Process SNOTEL data (if selected)
    if len(snotel_sel) > 0:

        # Process daily temperature and precip, create name list
        snotel_p_df = pd.DataFrame(index=dates)
        snotel_t_df = pd.DataFrame(index=dates)
        name_df = pd.DataFrame(index=snotel_sel)

        for s in snotel_sel:
            # Add name to name_df
            name_df.loc[s, "name"] = str(snotel_sites.loc[s, "site_no"]) + " " + snotel_sites.loc[
                s, "name"] + " (" + str(round(snotel_sites.loc[s, "elev_ft"], 0)) + " ft)"

            # Import SNOTEL data
            if offline:
                snotel_in = screen_snotel(f"snotel_{s}", start_date, end_date)
            else:
                snotel_in = import_snotel(s,snotel_sites,vars=["TAVG", "PREC"])

            # Merge and add to temp and precip df
            snotel_t_in = snotel_t_df.merge(snotel_in["TAVG"], left_index=True, right_index=True, how="left")
            snotel_t_df.loc[:, s] = snotel_t_in["TAVG"]
            snotel_p_in = snotel_p_df.merge(snotel_in["PREC"], left_index=True, right_index=True, how="left")
            snotel_p_df.loc[:, s] = snotel_p_in["PREC"]

        # Calculate maximum values (for plotting axes)
        snotel_t_max = snotel_t_df.max().max()
        snotel_t_min = snotel_t_df.min().min()
        snotel_p_max = snotel_p_df.max().max()

    else:
        snotel_t_max = np.nan
        snotel_t_min = np.nan
        snotel_p_max = np.nan

    ## Process CSAS data (if selected)

    csas_t_df = pd.DataFrame()
    csas_a_df = pd.DataFrame()

    for site in csas_sel:
        if offline:
            csas_df = screen_csas(site, start_date, end_date,dtype)
        else:
            csas_df = import_csas_live(site, start_date, end_date,dtype)

        if site != "SBSG":
            csas_t_df[site] = csas_df["temp"]
        if (plot_albedo) and (site != "SBSG") and (site != "PTSP"):
            csas_a_df[site] = csas_df["albedo"]

    csas_max = np.nanmax([csas_t_df.max().max(),csas_a_df.max().max()])

    # Process NDFD, if selected

    # Filter data
    mint = maxt = qpf = rhm = sky = pop12 = False
    ndfd_max = ndfd_min = ndfd_qpf = 0

    if (basin != None) or (len(forecast_sel)>0):

        # check if there are still items
        if len(forecast_sel) > 0:

            if dtype=="iv":
                step="D"
            elif dtype=="dv":
                step="D"

            ndfd_max = ndfd_min = ndfd_qpf = np.nan

            mint = maxt = qpf = pop12 = False
            for sensor in forecast_sel:

                if sensor in ["snow","rhm","sky","flow"]:
                    continue

                df = screen_spatial(sensor,start_date,end_date,basin,aspects,elrange,slopes,"Date")
                if df.empty:
                    continue
                else:
                    # Calculate basin average values
                    ba_ndfd = ba_stats_std(df, "Date")
                    ba_ndfd = ba_ndfd.tz_localize(tz="utc")

                    #if sensor!="qpf":
                    ba_ndfd = ba_ndfd['mean'].resample(step).mean()
                    #else:
                    #    ba_ndfd = ba_ndfd['mean'].resample(step).sum()

                    ndfd = pd.DataFrame(index=dates)

                    if sensor=="mint":
                        mint = ndfd.merge(ba_ndfd,left_index=True,right_index=True,how="left")
                        ndfd_min = mint.min().item()

                    if sensor=="maxt":
                        maxt = ndfd.merge(ba_ndfd,left_index=True,right_index=True,how="left")
                        ndfd_max = maxt.min().item()

                    if sensor=="pop12":
                        pop12 = ndfd.merge(ba_ndfd,left_index=True,right_index=True,how="left")
                        pop12 = ba_ndfd

                    if sensor == "qpf":
                        qpf = ndfd.merge(ba_ndfd,left_index=True,right_index=True,how="left")
                        ndfd_qpf = qpf.min().item()


    # Calculate plotting axes values
    ymin = np.nanmin([ndfd_min,snotel_t_min, 0])
    ymax = np.nanmax([ndfd_max,snotel_t_max, csas_max, freeze]) * 1.25
    ymax2 = np.nanmax([ndfd_qpf,snotel_p_max, 1]) * 2

    # Create figure
    print("Updating meteorology plot...")
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates,
        y=[freeze] * len(dates),
        showlegend=False,
        text="Degrees (F)",
        mode='lines',
        line=dict(color='grey', dash="dash"),
        name=str(freeze) + "F",
        yaxis="y1"
    ))

    for s in snotel_sel:
        fig.add_trace(go.Bar(
            x=snotel_p_df.index,
            y=snotel_p_df.loc[:, s],
            marker_color=snotel_sites.loc[s, "prcp_color"],
            text="Precip (in)",
            showlegend=False,
            name=name_df.loc[s, "name"] + " Daily Precip.",
            yaxis="y2"
        ))

        fig.add_trace(go.Scatter(
            x=snotel_t_df.index,
            y=snotel_t_df.loc[:, s],
            mode='lines',
            line=dict(color=snotel_sites.loc[s, "color"]),
            text="Degrees (F)",
            name=name_df.loc[s, "name"] + " Avg. Temp.",
            yaxis="y1"
        ))

    if qpf is not False:
        fig.add_trace(go.Bar(
            x=qpf.index,
            y=qpf.loc[:,"mean"],
            marker_color="black",
            text="NWS QPF (in)",
            showlegend=True,
            name="NWS Mean Precip Forecast for selection",
            yaxis="y2"
        ))

    for c in csas_t_df.columns:
        fig.add_trace(go.Scatter(
            x=csas_t_df.index,
            y=csas_t_df[c],
            text="Degrees (F)",
            mode='lines',
            line=dict(color=csas_gages.loc[c, "color"],dash="dot"),
            name=c+" Avg. Temp.",
            yaxis="y1"))
    if plot_albedo == True:
        for c in csas_a_df.columns:
            fig.add_trace(go.Scatter(
                x=csas_a_df.index,
                y=(1-csas_a_df[c])*100,
                text="100% - Albedo",
                mode='lines',
                line=dict(color=csas_gages.loc[c, "color"],dash="dash"),
                name=c+" 100% - Albedo",
                yaxis="y1"))

    if mint is not False:
        fig.add_trace(ba_mean_plot(mint, f"Min Temp", "blue"))

    if maxt is not False:
        fig.add_trace(ba_mean_plot(maxt, f"Max Temp", "red"))

    if pop12 is not False:
        fig.add_trace(go.Scatter(
            x=pop12.index,
            y=[ymax-ymax2]*len(pop12),
            mode="text",
            textfont=dict(
                color="grey"
            ),
            line=dict(color="grey"),
            text=round(pop12,0),
            name="Precip. Prob. (%)",
            showlegend=False,
            yaxis="y1"
        ))

    fig.add_trace(shade_forecast(ymax))

    fig.update_layout(
        margin={'l': 40, 'b': 40, 't': 0, 'r': 45},
        height=400,
        legend={'x': 0, 'y': 1, 'bgcolor': 'rgba(255,255,255,0.8)'},
        hovermode='closest',
        plot_bgcolor='white',
        xaxis=dict(
            range=[dates.min(), dates.max()],
            showline=True,
            linecolor="black",
            mirror=True
        ),
        yaxis=dict(
            title="Temperature (deg F)",
            range=[ymin, ymax],
            showline=True,
            linecolor="black",
            mirror=True
        ),
        yaxis2=dict(
            title="Precipitation (in)",
            side="right",
            overlaying='y',
            range=[ymax2, 0]
        )
    )
    return fig
