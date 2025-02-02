#!/usr/bin/env python3
import multiprocessing
import sys
import warnings
from functools import partial

import pysam
from tqdm import tqdm

from pydamage import __version__, damage, utils
from pydamage.accuracy_model import glm_predict, prepare_data
from pydamage.exceptions import PyDamageWarning
from pydamage.models import glm_model_params
from pydamage.plot import damageplot

# def pydamage_analyze(
#     bam,
#     wlen=30,
#     show_al=False,
#     process=1,
#     outdir="",
#     plot=False,
#     verbose=False,
#     force=False,
#     group=False,
# ):

#     if group:
#         pydamage_analyze_group(
#             bam, wlen, show_al, process, outdir, plot, verbose, force
#         )

#     else:
#         pydamage_analyze_multi(
#             bam, wlen, show_al, process, outdir, plot, verbose, force
#         )


def pydamage_analyze(
    bam,
    wlen=30,
    show_al=False,
    process=1,
    outdir="",
    plot=False,
    verbose=False,
    force=False,
    group=False,
    decimals=-1,
):
    """Runs the pydamage analysis for each reference separately

    Args:
        bam(str): Path to alignment (sam/bam/cram) file
        wlen(int): window length
        show_al(bool): print alignments representations
        process(int):  Number of  processes for parellel computing
        outdir(str): Path to output directory
        verbose(bool): verbose mode
        force(bool): force overwriting of results directory
    Returns:
        pd.DataFrame: pandas DataFrame containg pydamage results

    """
    if verbose:
        print(f"Pydamage version {__version__}\n")
    utils.makedir(outdir, force=force)

    refs, mode = utils.prepare_bam(bam)

    proc = min(len(refs), process)

    ##########################
    # Simple loop for debugging
    ##########################
    # filt_res = []
    # for ref in refs:
    #     res = damage.test_damage(
    #         bam=bam,
    #         ref=ref,
    #         wlen=wlen,
    #         show_al=show_al,
    #         mode=mode,
    #         process=process,
    #         verbose=verbose,
    #     )
    #     if res:
    #         filt_res.append(res)
    #     break
    ##########################
    ##########################

    test_damage_partial = partial(
        damage.test_damage,
        bam=bam,
        mode=mode,
        wlen=wlen,
        show_al=show_al,
        process=process,
        verbose=verbose,
    )
    print("Estimating and testing Damage")
    if group:
        filt_res = [
            damage.test_damage(
                ref=None,
                bam=bam,
                mode=mode,
                wlen=wlen,
                show_al=show_al,
                process=process,
                verbose=verbose,
            )
        ]
    else:
        with multiprocessing.Pool(proc) as p:
            res = list(tqdm(p.imap(test_damage_partial, refs), total=len(refs)))
        filt_res = [i for i in res if i]

    print(f"{len(filt_res)} contig(s) successfully analyzed by Pydamage")
    if len(filt_res) == 0:
        warnings.warn(
            "No alignments were found, check your alignment file", PyDamageWarning
        )

    if plot and len(filt_res) > 0:
        print("\nGenerating Pydamage plots")
        plotdir = f"{outdir}/plots"
        utils.makedir(plotdir, confirm=False)

        plot_partial = partial(damageplot, outdir=plotdir, wlen=wlen)
        with multiprocessing.Pool(proc) as p:
            list(tqdm(p.imap(plot_partial, filt_res), total=len(filt_res)))
    df_pydamage = utils.pandas_processing(res_dict=filt_res, wlen=wlen)

    prep_df_glm = prepare_data(df_pydamage)
    df_glm = glm_predict(prep_df_glm, glm_model_params)

    df = df_glm.merge(df_pydamage, left_index=True, right_index=True)

    utils.df_to_csv(df, outdir, decimals=decimals)
    return df
