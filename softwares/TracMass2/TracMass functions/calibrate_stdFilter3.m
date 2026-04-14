function f = calibrate_stdFilter3(gaussf,width, n)
%Magnus Åberg
if nargin < 3
    n = 1e4;
end


s = randn('state');
randn('state',314); %initialize the random number generator to get identical results each time
x = randn(n,1);
xs = maFilt(x,gaussf(:));
randn('state',s);

err0 = stdFilter3(1:numel(x), x-xs, width);
err1 = std(x);

f = err1/mean(err0);
