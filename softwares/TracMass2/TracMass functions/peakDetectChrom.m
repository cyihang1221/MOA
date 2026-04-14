function [ peak, extra ] = peakDetectChrom( chrom, param )

%by: Magnus Åberg

dt = median( diff( chrom.time ) );

zaf = mk_zaf2( dt, param.zafSigma, param.zafWidth );
zaf2 = mk_zaf2( dt, param.zaf2Sigma, param.zafWidth );
gauss = mk_gauss( dt, param.gaussSigma, param.gaussWidth );

[ inds, extra ] = zafPeakDetect2_2( chrom.intensity(:), zaf, zaf2,...
    gauss, param.stdFiltWidth, param.nSignalToNoise, param.f, false );
extra.time = chrom.time;
nPeak = numel( inds );
peak = mkPeakList2( chrom, inds, gauss );
peak.id  = ( 1 : nPeak )';
end
