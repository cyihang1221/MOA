function f=CalibrateStandardFilter(obj)
%Magnus Åberg
    gauss=mk_gauss(obj.dt,obj.gaussSigma,obj.gaussWidth);
    f = calibrate_stdFilter3(gauss,obj.stdFiltWidth);
