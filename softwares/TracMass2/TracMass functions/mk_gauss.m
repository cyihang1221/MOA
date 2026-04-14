function [gauss]=mk_gauss(dt,sigma,width)
%gauss=mk_gauss(dt,sigma,width)
%
% dt - delta time between measurements (in seconds).
% sigma - standard deviation of peaks  (in seconds).
% width - width of filter in units of sigma, e.g. 4 means +/-4 sigma
% width.

%by: Magnus Åberg

time = 0:dt:width*sigma;
time = [-fliplr(time(2:end)), time];
time = time(:);

x = time/sigma;
gauss = exp(-1/2*x.^2);
gauss = gauss / sum(gauss);

