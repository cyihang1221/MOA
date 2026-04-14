function [inds,extra] = zafPeakDetect2_2(x,zaf,zaf2,gauss,stdFiltWidth,nStd,f,DEBUG)

%by: Magnus Åberg

try
nErr = nStd;
do_debug = false;
if nargin>7,
   do_debug = DEBUG;
end
x = x(:);
xs = maFilt(x,gauss(:));
extra.xs = xs;
z = maFilt(xs,zaf(:));
extra.z1 = z;
z2 = maFilt(xs,zaf2(:));
extra.z2 = z2;
z = max([z,z2],[],2);
extra.z = z;
N = numel(x);

%err0 = stdFilter(1:numel(x), x-xs, stdFiltWidth)*f; % f is calibrated for the parameters used ("gauss" and "stdFiltWidth")
err0 = stdFilter3(1:numel(x), xs-maFilt(x,[1 2 1]'/4), stdFiltWidth)*f; % f is calibrated for the parameters used ("gauss" and "stdFiltWidth")
extra.err0 = err0*nErr;
err1 = sqrt(x);
extra.err1 = err1*nErr;
err = max([err0(:)'; err1(:)'])';% poisson stats gives sqrt(x) as lower bound for the error
err = maFilt(err,mk_gauss(1,stdFiltWidth,3.5));
extra.err = err*nErr;
z0=z;
z(z<nErr*err)=0;

[m,inds]=maxima(maFilt(z,[.5 1 .5]'/2)); % to avoids peak detected on almost adjacent data points
mask = inds==1 | inds==N; % no peaks in the first or last data point.
inds(mask)=[];
m(mask)=[];

if do_debug
   fig=figure(239576534);clf, hold on
   plot([z0,x,xs])
   plot(1:N,err0*nErr,'r:')
   plot(1:N,err1*nErr,'m:')
   plot(err*nErr,'c:')
   plot(inds,m,'ro','markerfacecolor','r')
   plot(inds,x(inds),'c+')
   disp('Press <F5> to continue or type "dbquit<enter>" to quit.')
   keyboard
end
catch
   reportError;
end

