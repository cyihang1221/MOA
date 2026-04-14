function [C,m]=mean_center(X)
%[C,m]=mean_center(X)
% centers the columns of X.

%by: Magnus Åberg
m = mean(X,1);
C= X - ones(size(X,1),1)*m;
m = m';