function [zaf]=mk_zaf(dt,zafsigma,zafwidth)
%zaf=mk_zaf(dt,zafsigma,zafwidth)
%
% dt - delta time between measurements (in seconds).
% zafsigma - standard deviation of peaks (and the zaf) (in seconds).
% zafwidth - width of zaf in units of zafsigma, e.g. 4 means +/-4 sigma
% width.

%by: Magnus Åberg
time = 0:dt:zafwidth*zafsigma;
time = [-fliplr(time(2:end)), time];
time = time(:);

x = time/zafsigma;
zaf = exp(-1/2*x.^2)-x.^2.*exp(-1/2*x.^2);
%zaf(zaf<0) = zaf(zaf<0)*sum(zaf(zaf>0))/abs(sum(zaf(zaf<0)));
zaf = zaf-mean(zaf);
%zaf = 2*zaf/sum(abs(zaf));
zaf = zaf/norm(zaf);
%sum(zaf)

